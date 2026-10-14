"""
Antigravity Quota Monitor Engine.

Monitors 5-hour rolling limits and quotas for Antigravity AI accounts:
- Extracts live OAuth access token and account email from macOS Keychain (or token file fallback).
- Queries Google Cloud Code API (v1internal:fetchAvailableModels) for live quota fractions and reset times.
- In-memory TTL cache (60 seconds) to guarantee 0.0% CPU overhead and zero redundant network requests.
- Triggers alert structures when remaining quota drops below the specified threshold (< 20%).
- Provides formatted multi-model status reports for /quota and /limits commands.
"""

import os
import re
import json
import time
import base64
import logging
import datetime
import subprocess
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger("AntigravityQuotaMonitor")

API_SUMMARY_ENDPOINT = "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary"
API_MODELS_ENDPOINT = "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
API_ENDPOINT = API_MODELS_ENDPOINT  # Backwards compatibility
KEYCHAIN_SERVICE = "gemini"
KEYCHAIN_ACCOUNT = "antigravity"
TOKEN_FILE_FALLBACK = os.path.expanduser("~/.gemini/jetski-standalone-oauth-token")
APP_STORAGE_FALLBACK = os.path.expanduser("~/Library/Application Support/Antigravity/app_storage.json")

CACHE_TTL_SECONDS = 60.0


@dataclass
class QuotaBucket:
    bucket_id: str
    display_name: str
    window: str  # e.g. "5h", "weekly"
    remaining_fraction: float  # e.g. 0.897 -> 89.7%
    reset_time: Optional[datetime.datetime]  # UTC datetime
    raw_reset_str: Optional[str] = None
    description: Optional[str] = None


@dataclass
class QuotaGroup:
    group_id: str
    display_name: str
    buckets: Dict[str, QuotaBucket] = field(default_factory=dict)
    description: Optional[str] = None


@dataclass
class ModelQuota:
    model_id: str
    display_name: str
    remaining_fraction: float  # e.g. 0.897 -> 89.7%
    reset_time: Optional[datetime.datetime]  # UTC datetime
    raw_reset_str: Optional[str] = None


@dataclass
class QuotaSnapshot:
    email: str
    groups: Dict[str, QuotaGroup] = field(default_factory=dict)
    models: Dict[str, ModelQuota] = field(default_factory=dict)
    fetched_at: float = field(default_factory=time.monotonic)


@dataclass
class QuotaAlert:
    email: str
    model_name: str
    percent_left: float
    time_left_str: str
    reset_time_str: str


class QuotaMonitor:
    def __init__(self, cache_ttl: float = CACHE_TTL_SECONDS):
        self.cache_ttl = cache_ttl
        self._cached_snapshot: Optional[QuotaSnapshot] = None
        self._last_fetch_time: float = 0.0

    def get_auth_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts OAuth access token and active user email.
        Primary source: macOS Keychain (service='gemini', account='antigravity').
        Fallback 1: ~/.gemini/jetski-standalone-oauth-token
        Fallback 2: ~/Library/Application Support/Antigravity/app_storage.json (email only)
        """
        access_token: Optional[str] = None
        email: Optional[str] = None

        # 1. Primary: macOS Keychain
        try:
            res = subprocess.run(
                ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w"],
                capture_output=True,
                text=True,
                timeout=2.0
            )
            if res.returncode == 0 and res.stdout.strip():
                raw_val = res.stdout.strip()
                if raw_val.startswith("go-keyring-base64:"):
                    b64_str = raw_val[len("go-keyring-base64:"):]
                    raw_json = base64.b64decode(b64_str).decode("utf-8")
                    data = json.loads(raw_json)
                    token_data = data.get("token", {})
                    access_token = token_data.get("access_token")
                    
                    id_token = data.get("id_token", "")
                    if id_token and "." in id_token:
                        parts = id_token.split(".")
                        if len(parts) >= 2:
                            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                            jwt_payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
                            email = jwt_payload.get("email")
        except Exception as e:
            logger.debug(f"Keychain read skipped or failed: {e}")

        # 2. Fallback: Local JSON token file
        if not access_token and os.path.exists(TOKEN_FILE_FALLBACK):
            try:
                with open(TOKEN_FILE_FALLBACK, "r", encoding="utf-8") as f:
                    tdata = json.load(f)
                    tok = tdata.get("token", {})
                    if isinstance(tok, str):
                        try:
                            tok = json.loads(tok)
                        except Exception:
                            pass
                    if isinstance(tok, dict):
                        access_token = tok.get("access_token")

                    id_token = tdata.get("id_token", "")
                    if id_token and "." in id_token and not email:
                        parts = id_token.split(".")
                        if len(parts) >= 2:
                            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                            jwt_payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
                            email = jwt_payload.get("email")
            except Exception as e:
                logger.debug(f"Fallback token file read error: {e}")

        # 3. Fallback email from app_storage.json
        if not email and os.path.exists(APP_STORAGE_FALLBACK):
            try:
                with open(APP_STORAGE_FALLBACK, "r", encoding="utf-8") as f:
                    app_data = json.load(f)
                    email = app_data.get("jetski.onboarding.lastLoginUsername")
            except Exception:
                pass

        return access_token, email

    def fetch_live_quotas(
        self,
        force_refresh: bool = False,
        timeout: float = 3.5
    ) -> Optional[QuotaSnapshot]:
        """
        Queries Google Cloud Code API for live quotas across all models and groups.
        Uses in-memory cache to prevent unnecessary calls within TTL window.
        """
        now = time.monotonic()
        if not force_refresh and self._cached_snapshot:
            if (now - self._last_fetch_time) < self.cache_ttl:
                return self._cached_snapshot

        access_token, email = self.get_auth_credentials()
        if not access_token:
            logger.debug("No OAuth access token available for quota check.")
            return self._cached_snapshot

        parsed_groups: Dict[str, QuotaGroup] = {}
        parsed_models: Dict[str, ModelQuota] = {}

        # 1. Primary: retrieveUserQuotaSummary (contains both 5-hour and weekly buckets)
        try:
            req_summary = urllib.request.Request(
                API_SUMMARY_ENDPOINT,
                data=b"{}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "antigravity/1.2.11"
                }
            )
            with urllib.request.urlopen(req_summary, timeout=timeout) as resp:
                if resp.status == 200:
                    raw_data = resp.read().decode("utf-8")
                    data = json.loads(raw_data)
                    for g in data.get("groups", []):
                        disp_name = g.get("displayName", "AI Models")
                        g_desc = g.get("description")
                        name_l = disp_name.lower()
                        if "gemini" in name_l:
                            group_id = "gemini"
                        elif "claude" in name_l or "gpt" in name_l or "3p" in name_l:
                            group_id = "3p"
                        else:
                            group_id = re.sub(r"[^a-zA-Z0-9_]+", "_", name_l).strip("_")

                        group_buckets: Dict[str, QuotaBucket] = {}
                        for b in g.get("buckets", []):
                            bid = b.get("bucketId", "")
                            b_name = b.get("displayName", bid)
                            window = b.get("window", "")
                            if not window:
                                if "5h" in bid:
                                    window = "5h"
                                elif "weekly" in bid:
                                    window = "weekly"
                                else:
                                    window = bid

                            rem_frac = b.get("remainingFraction")
                            if rem_frac is None:
                                continue

                            reset_str = b.get("resetTime")
                            reset_dt = None
                            if reset_str:
                                try:
                                    clean_str = reset_str.replace("Z", "+00:00")
                                    reset_dt = datetime.datetime.fromisoformat(clean_str)
                                except Exception:
                                    pass

                            group_buckets[window] = QuotaBucket(
                                bucket_id=bid,
                                display_name=b_name,
                                window=window,
                                remaining_fraction=float(rem_frac),
                                reset_time=reset_dt,
                                raw_reset_str=reset_str,
                                description=b.get("description")
                            )

                        parsed_groups[group_id] = QuotaGroup(
                            group_id=group_id,
                            display_name=disp_name,
                            buckets=group_buckets,
                            description=g_desc
                        )

                        # Populate parsed_models with 5h quota for compatibility
                        if "5h" in group_buckets:
                            b_5h = group_buckets["5h"]
                            if group_id == "gemini":
                                parsed_models["gemini"] = ModelQuota("gemini", "Gemini Models", b_5h.remaining_fraction, b_5h.reset_time, b_5h.raw_reset_str)
                                parsed_models["gemini-pro"] = ModelQuota("gemini-pro", "Gemini Pro", b_5h.remaining_fraction, b_5h.reset_time, b_5h.raw_reset_str)
                                parsed_models["gemini-flash"] = ModelQuota("gemini-flash", "Gemini Flash", b_5h.remaining_fraction, b_5h.reset_time, b_5h.raw_reset_str)
                            elif group_id == "3p":
                                parsed_models["claude"] = ModelQuota("claude", "Claude Models", b_5h.remaining_fraction, b_5h.reset_time, b_5h.raw_reset_str)
                                parsed_models["gpt"] = ModelQuota("gpt", "GPT Models", b_5h.remaining_fraction, b_5h.reset_time, b_5h.raw_reset_str)
                            else:
                                parsed_models[group_id] = ModelQuota(group_id, disp_name, b_5h.remaining_fraction, b_5h.reset_time, b_5h.raw_reset_str)
        except Exception as e:
            logger.debug(f"Primary retrieveUserQuotaSummary failed or unavailable: {e}")

        # 2. Fallback: fetchAvailableModels (if primary endpoint was empty or failed)
        if not parsed_groups:
            try:
                req_models = urllib.request.Request(
                    API_MODELS_ENDPOINT,
                    data=b"{}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "User-Agent": "antigravity/1.2.11"
                    }
                )
                with urllib.request.urlopen(req_models, timeout=timeout) as resp:
                    if resp.status == 200:
                        raw_data = resp.read().decode("utf-8")
                        data_models = json.loads(raw_data)
                        models_data = data_models.get("models", {})
                        for model_id, info in models_data.items():
                            quota_info = info.get("quotaInfo")
                            if not quota_info:
                                continue

                            rem_frac = quota_info.get("remainingFraction")
                            if rem_frac is None:
                                continue

                            reset_str = quota_info.get("resetTime")
                            reset_dt = None
                            if reset_str:
                                try:
                                    clean_str = reset_str.replace("Z", "+00:00")
                                    reset_dt = datetime.datetime.fromisoformat(clean_str)
                                except Exception:
                                    pass

                            display_name = info.get("displayName", model_id)
                            parsed_models[model_id] = ModelQuota(
                                model_id=model_id,
                                display_name=display_name,
                                remaining_fraction=float(rem_frac),
                                reset_time=reset_dt,
                                raw_reset_str=reset_str
                            )
            except Exception as e:
                logger.debug(f"Fallback fetchAvailableModels failed: {e}")

        if not parsed_groups and not parsed_models:
            return self._cached_snapshot

        snapshot = QuotaSnapshot(
            email=email or "Antigravity Account",
            groups=parsed_groups,
            models=parsed_models,
            fetched_at=now
        )

        self._cached_snapshot = snapshot
        self._last_fetch_time = now
        return snapshot

    def check_quota_alert(
        self,
        current_model: str = "",
        threshold: float = 0.20,
        lang: str = "ru"
    ) -> Optional[QuotaAlert]:
        """
        Determines if the active model (or family) has 5-hour rolling quota below threshold (default 20%).
        Returns QuotaAlert if alert should be triggered, otherwise None.
        Weekly quota is explicitly excluded here — only the 5h window triggers the warning.
        """
        try:
            snapshot = self.fetch_live_quotas()
            if not snapshot:
                return None

            target_quota: Optional[ModelQuota] = None
            norm_model = current_model.lower().replace("_", "-")

            # 1. If groups are available, check 5h bucket directly for model family
            if snapshot.groups:
                if "claude" in norm_model or "gpt" in norm_model or "3p" in norm_model:
                    grp = snapshot.groups.get("3p")
                else:
                    grp = snapshot.groups.get("gemini")

                if grp and "5h" in grp.buckets:
                    b_5h = grp.buckets["5h"]
                    target_quota = ModelQuota(
                        model_id=b_5h.bucket_id,
                        display_name=grp.display_name,
                        remaining_fraction=b_5h.remaining_fraction,
                        reset_time=b_5h.reset_time,
                        raw_reset_str=b_5h.raw_reset_str
                    )

            # 2. Fallback to models dictionary if not matched via groups
            if not target_quota and snapshot.models:
                candidates: List[ModelQuota] = []
                for mid, mquota in snapshot.models.items():
                    mid_norm = mid.lower().replace("_", "-")
                    dname_norm = mquota.display_name.lower().replace("_", "-")
                    if norm_model and (norm_model in mid_norm or norm_model in dname_norm or mid_norm in norm_model):
                        candidates.append(mquota)

                if candidates:
                    target_quota = min(candidates, key=lambda q: q.remaining_fraction)
                else:
                    if "claude" in norm_model:
                        family = [q for mid, q in snapshot.models.items() if "claude" in mid.lower()]
                    elif "gpt" in norm_model:
                        family = [q for mid, q in snapshot.models.items() if "gpt" in mid.lower()]
                    else:
                        family = [q for mid, q in snapshot.models.items() if "gemini" in mid.lower()]

                    if family:
                        target_quota = min(family, key=lambda q: q.remaining_fraction)
                    else:
                        target_quota = min(snapshot.models.values(), key=lambda q: q.remaining_fraction)

            if not target_quota:
                return None

            if target_quota.remaining_fraction >= threshold:
                return None

            # 5-hour quota is strictly below threshold!
            percent_left = target_quota.remaining_fraction * 100.0

            time_left_str = "—"
            reset_time_str = "—"

            if target_quota.reset_time:
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                delta = target_quota.reset_time - now_utc
                total_sec = max(0, int(delta.total_seconds()))

                hours = total_sec // 3600
                minutes = (total_sec % 3600) // 60

                if hours > 0:
                    time_left_str = f"{hours} ч {minutes} мин" if lang == "ru" else f"{hours}h {minutes}m"
                elif minutes > 0:
                    time_left_str = f"{minutes} мин" if lang == "ru" else f"{minutes}m"
                else:
                    time_left_str = "менее минуты" if lang == "ru" else "less than 1m"

                # Convert to local time for user readability
                local_dt = target_quota.reset_time.astimezone()
                reset_time_str = local_dt.strftime("%H:%M")

            return QuotaAlert(
                email=snapshot.email,
                model_name=target_quota.display_name,
                percent_left=percent_left,
                time_left_str=time_left_str,
                reset_time_str=reset_time_str
            )
        except Exception as e:
            logger.debug(f"check_quota_alert error (silenced): {e}")
            return None

    def get_summary_report(self, lang: str = "ru") -> str:
        """
        Builds a comprehensive, human-readable report of 5-hour and weekly quotas for /quota command.
        """
        snapshot = self.fetch_live_quotas(force_refresh=True)
        if not snapshot or (not snapshot.groups and not snapshot.models):
            return (
                "⚠️ Не удалось получить информацию о квотах.\n"
                "Убедитесь, что Antigravity CLI авторизован (<code>agy</code> работает)."
                if lang == "ru" else
                "⚠️ Failed to retrieve quota information.\n"
                "Please verify that Antigravity CLI is authenticated."
            )

        lines: List[str] = []
        if lang == "ru":
            lines.append("📊 <b>Лимиты Antigravity:</b>")
            lines.append(f"📧 <b>Аккаунт:</b> <code>{snapshot.email}</code>\n")
        else:
            lines.append("📊 <b>Antigravity Quotas:</b>")
            lines.append(f"📧 <b>Account:</b> <code>{snapshot.email}</code>\n")

        if snapshot.groups:
            # Order: Gemini Models first, then Claude and GPT models
            ordered_keys = []
            if "gemini" in snapshot.groups:
                ordered_keys.append("gemini")
            if "3p" in snapshot.groups:
                ordered_keys.append("3p")
            for k in snapshot.groups:
                if k not in ordered_keys:
                    ordered_keys.append(k)

            for gid in ordered_keys:
                grp = snapshot.groups[gid]
                icon_header = "💎" if gid == "gemini" else "🧠"
                lines.append(f"{icon_header} <b>{grp.display_name}:</b>")

                b_5h = grp.buckets.get("5h")
                if b_5h:
                    pct_5h = b_5h.remaining_fraction * 100.0
                    icon_5h = _get_fraction_icon(b_5h.remaining_fraction)
                    reset_5h = _format_reset_delta(b_5h.reset_time, b_5h.remaining_fraction, lang)
                    lbl_5h = "5-часовой" if lang == "ru" else "5-Hour"
                    lines.append(f"  ⏱ <b>{lbl_5h}:</b> {icon_5h} {pct_5h:.1f}%{reset_5h}")

                b_weekly = grp.buckets.get("weekly")
                if b_weekly:
                    pct_w = b_weekly.remaining_fraction * 100.0
                    icon_w = _get_fraction_icon(b_weekly.remaining_fraction)
                    reset_w = _format_reset_delta(b_weekly.reset_time, b_weekly.remaining_fraction, lang)
                    lbl_w = "Недельный" if lang == "ru" else "Weekly"
                    lines.append(f"  📅 <b>{lbl_w}:</b> {icon_w} {pct_w:.1f}%{reset_w}")

                lines.append("")
        else:
            # Fallback if only models dictionary is present
            families: Dict[str, List[ModelQuota]] = {
                "Gemini": [],
                "Claude": [],
                "GPT": []
            }
            for mid, q in snapshot.models.items():
                mid_l = mid.lower()
                if "claude" in mid_l:
                    families["Claude"].append(q)
                elif "gpt" in mid_l:
                    families["GPT"].append(q)
                elif "gemini" in mid_l:
                    families["Gemini"].append(q)

            for fam_name, q_list in families.items():
                if not q_list:
                    continue
                min_q = min(q_list, key=lambda item: item.remaining_fraction)
                pct = min_q.remaining_fraction * 100.0
                icon = _get_fraction_icon(min_q.remaining_fraction)
                reset_info = _format_reset_delta(min_q.reset_time, min_q.remaining_fraction, lang)
                lbl_5h = "5-часовой" if lang == "ru" else "5-Hour"
                lines.append(f"{icon} <b>{fam_name}:</b> {pct:.1f}%{reset_info}")
            lines.append("")

        if lang == "ru":
            lines.append("💡 <i>5-часовой лимит сглаживает нагрузку (при остатке &lt; 20% бот уведомит в ответе). Недельный лимит привязан к вашему тарифу.</i>")
        else:
            lines.append("💡 <i>The 5-hour limit smooths demand (alerts if remaining &lt; 20%). The weekly limit corresponds to your tier quota.</i>")

        return "\n".join(lines).strip()


def _get_fraction_icon(fraction: float) -> str:
    pct = fraction * 100.0
    if pct > 50.0:
        return "🟢"
    elif pct > 20.0:
        return "🟡"
    else:
        return "🔴"


def _format_reset_delta(reset_dt: Optional[datetime.datetime], remaining_fraction: float, lang: str) -> str:
    if remaining_fraction >= 1.0 or not reset_dt:
        return ""

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    delta = reset_dt - now_utc
    total_sec = max(0, int(delta.total_seconds()))
    if total_sec <= 0:
        return ""

    days = total_sec // 86400
    hours = (total_sec % 86400) // 3600
    minutes = (total_sec % 3600) // 60

    loc_dt = reset_dt.astimezone()
    loc_time_str = loc_dt.strftime("%H:%M")
    loc_date_time_str = loc_dt.strftime("%d.%m %H:%M")

    if days > 0:
        if lang == "ru":
            return f" <i>(Сброс через {days} дн {hours} ч, {loc_date_time_str})</i>"
        else:
            return f" <i>(Resets in {days}d {hours}h, on {loc_date_time_str})</i>"
    elif hours > 0:
        if lang == "ru":
            return f" <i>(Сброс через {hours} ч {minutes} мин, в {loc_time_str})</i>"
        else:
            return f" <i>(Resets in {hours}h {minutes}m, at {loc_time_str})</i>"
    elif minutes > 0:
        if lang == "ru":
            return f" <i>(Сброс через {minutes} мин, в {loc_time_str})</i>"
        else:
            return f" <i>(Resets in {minutes}m, at {loc_time_str})</i>"
    else:
        if lang == "ru":
            return " <i>(Сброс менее чем через минуту)</i>"
        else:
            return " <i>(Resets in less than 1m)</i>"


# Global singleton instance
quota_monitor = QuotaMonitor()
