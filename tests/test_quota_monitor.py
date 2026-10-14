import unittest
from unittest.mock import patch, MagicMock
import datetime
import json
import time

from src.engine.quota_monitor import (
    QuotaMonitor,
    ModelQuota,
    QuotaGroup,
    QuotaBucket,
    QuotaSnapshot,
    QuotaAlert
)
from src.bot.locales import t


class TestQuotaMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = QuotaMonitor(cache_ttl=60.0)

    def test_quota_alert_footer_localization(self):
        """Test localization string formatting for quota alert in both ru and en."""
        footer_ru = t(
            "quota_alert_footer",
            "ru",
            percent="14.8%",
            email="test@gmail.com",
            model="Gemini 3.8 Flash",
            time_left="1 ч 24 мин",
            reset_time="14:48"
        )
        self.assertIn("Лимит Antigravity подходит к концу (14.8%)", footer_ru)
        self.assertIn("test@gmail.com", footer_ru)
        self.assertIn("1 ч 24 мин", footer_ru)
        self.assertIn("14:48", footer_ru)

        footer_en = t(
            "quota_alert_footer",
            "en",
            percent="14.8%",
            email="test@gmail.com",
            model="Gemini 3.8 Flash",
            time_left="1h 24m",
            reset_time="14:48"
        )
        self.assertIn("Antigravity 5h Quota Alert (14.8% left)", footer_en)
        self.assertIn("test@gmail.com", footer_en)
        self.assertIn("1h 24m", footer_en)

    @patch.object(QuotaMonitor, "get_auth_credentials")
    @patch("urllib.request.urlopen")
    def test_fetch_live_quotas_parsing(self, mock_urlopen, mock_creds):
        """Test API JSON parsing and model quota extraction."""
        mock_creds.return_value = ("fake_token_123", "user@test.org")

        mock_api_response = {
            "models": {
                "gemini-3.8-flash-tiered": {
                    "displayName": "Gemini 3.8 Flash",
                    "quotaInfo": {
                        "remainingFraction": 0.155,
                        "resetTime": "2026-09-25T15:30:00Z"
                    }
                },
                "claude-sonnet-4-6": {
                    "displayName": "Claude Sonnet 4.6 (Thinking)",
                    "quotaInfo": {
                        "remainingFraction": 0.85,
                        "resetTime": "2026-09-25T16:00:00Z"
                    }
                }
            }
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_api_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        snapshot = self.monitor.fetch_live_quotas(force_refresh=True)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.email, "user@test.org")
        self.assertIn("gemini-3.8-flash-tiered", snapshot.models)
        self.assertIn("claude-sonnet-4-6", snapshot.models)

        gemini_q = snapshot.models["gemini-3.8-flash-tiered"]
        self.assertAlmostEqual(gemini_q.remaining_fraction, 0.155, places=3)
        self.assertIsNotNone(gemini_q.reset_time)
        self.assertEqual(gemini_q.reset_time.year, 2026)

    def test_check_quota_alert_triggers_below_threshold(self):
        """Verify alert triggers when remaining quota is < 20%."""
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1, minutes=20)
        snapshot = QuotaSnapshot(
            email="alert_user@gmail.com",
            models={
                "gemini-3.8-flash": ModelQuota(
                    model_id="gemini-3.8-flash",
                    display_name="Gemini 3.8 Flash",
                    remaining_fraction=0.145,  # 14.5%
                    reset_time=future_time
                )
            }
        )
        self.monitor._cached_snapshot = snapshot
        self.monitor._last_fetch_time = time.monotonic()

        alert = self.monitor.check_quota_alert(current_model="gemini-3.8-flash", threshold=0.20, lang="ru")
        self.assertIsNotNone(alert)
        self.assertEqual(alert.email, "alert_user@gmail.com")
        self.assertAlmostEqual(alert.percent_left, 14.5, places=1)
        self.assertIn("мин", alert.time_left_str)

    def test_check_quota_alert_does_not_trigger_above_threshold(self):
        """Verify alert does not trigger when remaining quota is >= 20%."""
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
        snapshot = QuotaSnapshot(
            email="safe_user@gmail.com",
            models={
                "gemini-3.8-flash": ModelQuota(
                    model_id="gemini-3.8-flash",
                    display_name="Gemini 3.8 Flash",
                    remaining_fraction=0.45,  # 45%
                    reset_time=future_time
                )
            }
        )
        self.monitor._cached_snapshot = snapshot
        self.monitor._last_fetch_time = time.monotonic()

        alert = self.monitor.check_quota_alert(current_model="gemini-3.8-flash", threshold=0.20, lang="ru")
        self.assertIsNone(alert)

    def test_cache_ttl_avoids_repeated_fetches(self):
        """Verify that cache within TTL returns immediately without network calls."""
        snapshot = QuotaSnapshot(
            email="cached@gmail.com",
            models={},
            fetched_at=time.monotonic()
        )
        self.monitor._cached_snapshot = snapshot
        self.monitor._last_fetch_time = time.monotonic()

        with patch("urllib.request.urlopen") as mock_url:
            res = self.monitor.fetch_live_quotas(force_refresh=False)
            self.assertEqual(res.email, "cached@gmail.com")
            mock_url.assert_not_called()

    def test_summary_report_generation(self):
        """Verify get_summary_report formats multi-family overview with status emojis."""
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2, minutes=10)
        snapshot = QuotaSnapshot(
            email="dev@agency.ru",
            models={
                "gemini-3.8-flash-tiered": ModelQuota(
                    model_id="gemini-3.8-flash-tiered",
                    display_name="Gemini 3.8 Flash",
                    remaining_fraction=0.88,
                    reset_time=future_time
                ),
                "claude-sonnet-4-6": ModelQuota(
                    model_id="claude-sonnet-4-6",
                    display_name="Claude Sonnet 4.6",
                    remaining_fraction=1.0,
                    reset_time=future_time
                )
            }
        )

        with patch.object(self.monitor, "fetch_live_quotas", return_value=snapshot):
            report_ru = self.monitor.get_summary_report(lang="ru")
            self.assertIn("Лимиты Antigravity", report_ru)
            self.assertIn("dev@agency.ru", report_ru)
            self.assertIn("Gemini:", report_ru)
            self.assertIn("88.0%", report_ru)
            self.assertIn("Claude:", report_ru)
            self.assertIn("100.0%", report_ru)

            report_en = self.monitor.get_summary_report(lang="en")
            self.assertIn("Antigravity Quotas", report_en)
            self.assertIn("dev@agency.ru", report_en)

    @patch.object(QuotaMonitor, "get_auth_credentials")
    @patch("urllib.request.urlopen")
    def test_fetch_live_quotas_summary_with_weekly_buckets(self, mock_urlopen, mock_creds):
        """Test retrieveUserQuotaSummary parsing with 5h and weekly buckets."""
        mock_creds.return_value = ("fake_token_summary", "pro@antigravity.io")

        mock_api_summary = {
            "groups": [
                {
                    "displayName": "Gemini Models",
                    "buckets": [
                        {
                            "bucketId": "gemini-weekly",
                            "displayName": "Weekly Limit Remaining",
                            "window": "weekly",
                            "resetTime": "2026-09-30T03:09:59Z",
                            "remainingFraction": 0.433
                        },
                        {
                            "bucketId": "gemini-5h",
                            "displayName": "Five Hour Limit Remaining",
                            "window": "5h",
                            "resetTime": "2026-09-25T13:42:35Z",
                            "remainingFraction": 0.715
                        }
                    ]
                },
                {
                    "displayName": "Claude and GPT models",
                    "buckets": [
                        {
                            "bucketId": "3p-weekly",
                            "displayName": "Weekly Limit Remaining",
                            "window": "weekly",
                            "resetTime": "2026-10-02T10:14:57Z",
                            "remainingFraction": 1.0
                        },
                        {
                            "bucketId": "3p-5h",
                            "displayName": "Five Hour Limit Remaining",
                            "window": "5h",
                            "resetTime": "2026-09-25T15:14:57Z",
                            "remainingFraction": 1.0
                        }
                    ]
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_api_summary).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        snapshot = self.monitor.fetch_live_quotas(force_refresh=True)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.email, "pro@antigravity.io")
        self.assertIn("gemini", snapshot.groups)
        self.assertIn("3p", snapshot.groups)

        gemini_grp = snapshot.groups["gemini"]
        self.assertIn("5h", gemini_grp.buckets)
        self.assertIn("weekly", gemini_grp.buckets)
        self.assertAlmostEqual(gemini_grp.buckets["5h"].remaining_fraction, 0.715, places=3)
        self.assertAlmostEqual(gemini_grp.buckets["weekly"].remaining_fraction, 0.433, places=3)

    def test_summary_report_with_weekly_and_5h_limits(self):
        """Verify get_summary_report displays both 5-hour and weekly limits with time countdowns."""
        future_5h = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3, minutes=20)
        future_w = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=4, hours=12)

        snapshot = QuotaSnapshot(
            email="developer@company.com",
            groups={
                "gemini": QuotaGroup(
                    group_id="gemini",
                    display_name="Gemini Models",
                    buckets={
                        "5h": QuotaBucket("gemini-5h", "5h", "5h", 0.716, future_5h),
                        "weekly": QuotaBucket("gemini-weekly", "weekly", "weekly", 0.433, future_w)
                    }
                ),
                "3p": QuotaGroup(
                    group_id="3p",
                    display_name="Claude and GPT models",
                    buckets={
                        "5h": QuotaBucket("3p-5h", "5h", "5h", 1.0, future_5h),
                        "weekly": QuotaBucket("3p-weekly", "weekly", "weekly", 1.0, future_w)
                    }
                )
            }
        )

        with patch.object(self.monitor, "fetch_live_quotas", return_value=snapshot):
            report_ru = self.monitor.get_summary_report(lang="ru")
            self.assertIn("Лимиты Antigravity", report_ru)
            self.assertIn("developer@company.com", report_ru)
            self.assertIn("Gemini Models", report_ru)
            self.assertIn("5-часовой:", report_ru)
            self.assertIn("71.6%", report_ru)
            self.assertIn("Недельный:", report_ru)
            self.assertIn("43.3%", report_ru)
            self.assertIn("Claude and GPT models", report_ru)

            report_en = self.monitor.get_summary_report(lang="en")
            self.assertIn("Antigravity Quotas", report_en)
            self.assertIn("developer@company.com", report_en)
            self.assertIn("5-Hour:", report_en)
            self.assertIn("Weekly:", report_en)

    def test_check_quota_alert_ignores_weekly_low_quota(self):
        """Verify alert triggers strictly on 5h quota, ignoring low weekly quota."""
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        # 5h is 60% (healthy), weekly is 10% (low) -> NO alert
        snap_healthy_5h = QuotaSnapshot(
            email="user@test.com",
            groups={
                "gemini": QuotaGroup(
                    group_id="gemini",
                    display_name="Gemini Models",
                    buckets={
                        "5h": QuotaBucket("gemini-5h", "5h", "5h", 0.60, future_time),
                        "weekly": QuotaBucket("gemini-weekly", "weekly", "weekly", 0.10, future_time)
                    }
                )
            }
        )
        self.monitor._cached_snapshot = snap_healthy_5h
        self.monitor._last_fetch_time = time.monotonic()
        alert = self.monitor.check_quota_alert(current_model="gemini-2.5-pro", threshold=0.20, lang="ru")
        self.assertIsNone(alert)

        # 5h is 15% (low), weekly is 60% (healthy) -> ALERT triggers!
        snap_low_5h = QuotaSnapshot(
            email="user@test.com",
            groups={
                "gemini": QuotaGroup(
                    group_id="gemini",
                    display_name="Gemini Models",
                    buckets={
                        "5h": QuotaBucket("gemini-5h", "5h", "5h", 0.15, future_time),
                        "weekly": QuotaBucket("gemini-weekly", "weekly", "weekly", 0.60, future_time)
                    }
                )
            }
        )
        self.monitor._cached_snapshot = snap_low_5h
        self.monitor._last_fetch_time = time.monotonic()
        alert_triggered = self.monitor.check_quota_alert(current_model="gemini-2.5-pro", threshold=0.20, lang="ru")
        self.assertIsNotNone(alert_triggered)
        self.assertAlmostEqual(alert_triggered.percent_left, 15.0, places=1)


if __name__ == "__main__":
    unittest.main()
