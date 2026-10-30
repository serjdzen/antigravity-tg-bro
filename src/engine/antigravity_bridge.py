import os
import json
import codecs
import signal
import asyncio
import logging
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional, Set
from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
from src.engine.skills_loader import get_skills_paths
from src.config import settings

logger = logging.getLogger(__name__)

AGY_CLI_PATH = str(Path.home() / ".local" / "bin" / "agy")
CLI_BRAIN_DIR = Path.home() / ".gemini" / "antigravity-cli" / "brain"
CLI_SETTINGS_PATH = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"

DEFAULT_DENY_RULES = [
    "command(rm)",
    "command(rm *)",
    "command(rm*)",
    "command(rmdir)",
    "command(rmdir *)",
    "command(unlink *)",
    "command(git reset --hard)",
    "command(git reset --hard *)",
    "command(git clean -f*)",
    "command(sudo*)",
    "command(dd*)",
    "command(mkfs*)",
    "command(shutdown*)",
    "command(reboot*)"
]


def ensure_deny_integrity():
    """
    Startup Safety Guard: проверяет целостность правил deny в settings.json при старте бота.
    Гарантирует восстановление защиты даже после аварийного отключения питания Mac.
    """
    if not CLI_SETTINGS_PATH.exists():
        return
    try:
        data = json.loads(CLI_SETTINGS_PATH.read_text(encoding="utf-8"))
        current_deny = data.get("permissions", {}).get("deny", [])
        missing = [r for r in DEFAULT_DENY_RULES if r not in current_deny]
        if missing:
            data.setdefault("permissions", {})["deny"] = list(set(current_deny + DEFAULT_DENY_RULES))
            CLI_SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info("🛡️ Startup Safety Guard: правила Deny-листа успешно проверены и восстановлены.")
        else:
            logger.info("🛡️ Startup Safety Guard: Deny-список в порядке (защита активна).")
    except Exception as e:
        logger.error(f"Ошибка проверки целостности deny-листа: {e}")


def get_bot_agent_rules() -> str:
    """
    Загружает внутренние правила агента бота из data/agent_rules.md.
    Гарантирует точечное редактирование, detached-запуск серверов и форматирование для Telegram.
    """
    rules_path = Path(__file__).resolve().parent.parent.parent / "data" / "agent_rules.md"
    if rules_path.exists():
        try:
            return rules_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"Не удалось загрузить agent_rules.md: {e}")
    return ""


def get_subprocess_env() -> Dict[str, str]:
    """
    Формирует изолированное окружение для подпроцесса agy CLI с автоматическим
    подхватом системных прокси macOS (urllib.request.getproxies()), обеспечивая
    бесперебойную работу через активный VPN-туннель.
    """
    env = os.environ.copy()
    try:
        import urllib.request
        system_proxies = urllib.request.getproxies()
        for proto in ("https", "http", "all"):
            if proto in system_proxies and system_proxies[proto]:
                proxy_val = system_proxies[proto]
                if not proxy_val.startswith(("http://", "https://", "socks5://")):
                    proxy_val = f"http://{proxy_val}"
                env[f"{proto.upper()}_PROXY"] = proxy_val
                env[f"{proto}_proxy"] = proxy_val
    except Exception as e:
        logger.debug(f"Не удалось получить системные прокси: {e}")
    return env


@dataclass
class EngineEvent:
    event_type: str  # "conversation_id" | "thought" | "tool_call" | "token" | "error" | "done"
    content: Any


@contextlib.asynccontextmanager
async def temporary_deny_override(active: bool):
    """
    Контекстный менеджер для разового пропуска политик deny:
    - При active=True: временно очищает список deny в settings.json.
    - В finally: гарантированно возвращает исходный deny список обратно на диск.
    """
    if not active or not CLI_SETTINGS_PATH.exists():
        yield
        return

    original_deny = None
    try:
        data = json.loads(CLI_SETTINGS_PATH.read_text())
        original_deny = data.get("permissions", {}).get("deny", [])
        data["permissions"]["deny"] = []
        CLI_SETTINGS_PATH.write_text(json.dumps(data, indent=2))
        logger.info("🛡️ Deny-список временно отключен для разового Force Override.")
    except Exception as e:
        logger.warning(f"Не удалось временно очистить deny список: {e}")

    try:
        yield
    finally:
        if original_deny is not None:
            try:
                data = json.loads(CLI_SETTINGS_PATH.read_text())
                data["permissions"]["deny"] = original_deny if original_deny else DEFAULT_DENY_RULES
                CLI_SETTINGS_PATH.write_text(json.dumps(data, indent=2))
                logger.info("🛡️ Исходный Deny-список успешно восстановлен.")
            except Exception as e:
                logger.error(f"Не удалось восстановить deny список: {e}")


def get_existing_cli_conversation_ids() -> Set[str]:
    if CLI_BRAIN_DIR.exists():
        return {
            d.name for d in CLI_BRAIN_DIR.iterdir()
            if d.is_dir() and len(d.name) > 20 and not d.name.startswith(".")
        }
    return set()


def get_latest_cli_conversation_id(known_ids: Optional[Set[str]] = None) -> Optional[str]:
    if not CLI_BRAIN_DIR.exists():
        return None
    try:
        current_dirs = [
            d for d in CLI_BRAIN_DIR.iterdir()
            if d.is_dir() and len(d.name) > 20 and not d.name.startswith(".")
        ]
        if known_ids:
            new_dirs = [d for d in current_dirs if d.name not in known_ids]
            if new_dirs:
                new_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
                return new_dirs[0].name

        if current_dirs:
            current_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
            return current_dirs[0].name
    except Exception as e:
        logger.warning(f"Не удалось определить conversation_id из brain: {e}")
    return None


class AntigravityBridge:
    def __init__(self):
        self._active_agents: Dict[int, Any] = {}

    def cancel_active_task(self, user_id: int) -> bool:
        """
        Принудительно прерывает запущенный процесс agy CLI для указанного пользователя
        и уничтожает всю группу дочерних процессов (SIGTERM -> SIGKILL).
        """
        agent_proc = self._active_agents.get(user_id)
        if agent_proc:
            if isinstance(agent_proc, asyncio.subprocess.Process):
                try:
                    pgid = os.getpgid(agent_proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    agent_proc.kill()
                    os.killpg(pgid, signal.SIGKILL)
                    logger.info(f"⏹ Процесс задачи и группа pgid={pgid} для user {user_id} принудительно убиты.")
                    return True
                except ProcessLookupError:
                    return True
                except Exception as e:
                    logger.warning(f"Не удалось прервать процесс: {e}")
                    try:
                        agent_proc.kill()
                        return True
                    except Exception:
                        pass
        return False

    def is_agent_alive(self, user_id: int) -> bool:
        """
        Проверяет, запущен ли и активен ли сейчас процесс agy CLI для указанного пользователя.
        """
        agent_proc = self._active_agents.get(user_id)
        if not agent_proc:
            return False
        if hasattr(agent_proc, "returncode") and agent_proc.returncode is not None:
            return False
        pid = getattr(agent_proc, "pid", None)
        if pid is not None:
            try:
                os.kill(pid, 0)
                return True
            except (ProcessLookupError, OSError):
                return False
        return agent_proc.returncode is None

    async def stream_chat(
        self,
        user_id: int,
        prompt: str,
        project_dir: Path,
        model_name: Optional[str] = None,
        effort: str = "low",
        conversation_id: Optional[str] = None,
        engine_mode: str = "cli",
        force_override: bool = False,
        context_summary: Optional[str] = None
    ) -> AsyncGenerator[EngineEvent, None]:
        """
        Универсальный стриминг с непрерывной памятью сессий и контролем подтверждений:
        engine_mode == 'cli' -> запуск через автономный ~/.local/bin/agy в режиме text
        engine_mode == 'sdk' -> запуск через Python SDK
        force_override -> разовое снятие ограничений deny по явному согласованию пользователя
        """
        if engine_mode == "cli" and Path(AGY_CLI_PATH).exists():
            async for ev in self._stream_cli_chat(
                user_id=user_id,
                prompt=prompt,
                project_dir=project_dir,
                model_name=model_name,
                effort=effort,
                conversation_id=conversation_id,
                force_override=force_override,
                context_summary=context_summary
            ):
                yield ev
        else:
            async for ev in self._stream_sdk_chat(
                user_id=user_id,
                prompt=prompt,
                project_dir=project_dir,
                model_name=model_name
            ):
                yield ev

    async def generate_conversation_summary(
        self,
        conversation_id: str,
        project_dir: Path,
        model_name: Optional[str] = None,
        effort: str = "high",
        custom_focus: str = "",
        timeout_seconds: int = 240
    ) -> Optional[str]:
        """
        Генерирует нативное структурированное резюме сессии через agy CLI (Stateful Handover).
        Использует effort: high, чтобы модель вдумчиво выделила все ключевые нюансы и решения без потери контекста.
        """
        clean_effort = effort if effort in ["low", "medium", "high"] else "high"
        summary_prompt = (
            "Сформируй лаконичное, но ёмкое структурированное резюме (Executive Briefing) нашей текущей сессии "
            "для бесшовной передачи следующему агенту в чистый контекст (Stateful Handover). "
            "Не вызывай никаких инструментов, верни только готовый текст резюме.\n\n"
            "Структура резюме:\n"
            "### 🎯 Активная цель и текущий статус\n"
            "### 📝 Принятые решения, правила и договорённости\n"
            "### 📁 Ключевые затронутые файлы и данные\n"
            "### ⏳ На чём конкретно остановились (Следующие шаги)\n"
        )
        if custom_focus:
            summary_prompt += f"\nДополнительный приоритетный фокус от пользователя: {custom_focus}\n"

        cmd = [
            AGY_CLI_PATH,
            "--add-dir", str(project_dir),
            "--conversation", conversation_id,
            "-p", summary_prompt,
            "--effort", clean_effort,
            "--output-format", "text",
            "--dangerously-skip-permissions"
        ]

        if model_name:
            if "3.8" in model_name:
                cmd.extend(["--model", "gemini-3.8-flash"])
            elif "3.7" in model_name:
                cmd.extend(["--model", "gemini-3.7-flash"])
            elif "3.1" in model_name or "pro" in model_name.lower():
                cmd.extend(["--model", "gemini-3.1-pro"])
            elif "claude" in model_name.lower():
                cmd.extend(["--model", model_name])
            elif "flash" in model_name.lower():
                cmd.extend(["--model", "gemini-3.8-flash"])

        proc = None
        try:
            logger.info(
                f"Запуск генерации резюме для сессии {conversation_id} "
                f"(effort: {clean_effort}, таймаут: {timeout_seconds}с)..."
            )
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=get_subprocess_env()
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            summary_text = stdout_bytes.decode("utf-8", errors="replace").strip()
            if summary_text:
                logger.info(f"Резюме для сессии {conversation_id} успешно сгенерировано ({len(summary_text)} символов).")
                return summary_text
            else:
                err_text = stderr_bytes.decode("utf-8", errors="replace").strip()
                logger.warning(f"Команда agy вернула пустой вывод резюме: {err_text}")
                return None
        except asyncio.TimeoutError:
            logger.error(
                f"Таймаут ({timeout_seconds}с) при нативной генерации резюме сессии {conversation_id}. "
                f"Процесс CLI принудительно завершается."
            )
            if proc is not None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return None
        except Exception as exc:
            logger.error(f"Ошибка при нативной генерации резюме сессии: {exc!r}")
            if proc is not None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return None

    async def _stream_cli_chat(
        self,
        user_id: int,
        prompt: str,
        project_dir: Path,
        model_name: Optional[str] = None,
        effort: str = "low",
        conversation_id: Optional[str] = None,
        force_override: bool = False,
        context_summary: Optional[str] = None
    ) -> AsyncGenerator[EngineEvent, None]:
        clean_effort = effort if effort in ["low", "medium", "high"] else "low"
        logger.info(
            f"Запуск CLI сессии для user {user_id} в {project_dir} "
            f"(модель: {model_name}, effort: {clean_effort}, conv_id: {conversation_id}, override: {force_override})"
        )

        known_ids_before = get_existing_cli_conversation_ids()

        # Внедрение правил агента в рабочий процесс
        bot_rules = get_bot_agent_rules()
        effective_prompt = prompt
        if bot_rules:
            effective_prompt = f"<system_invariants>\n{bot_rules}\n</system_invariants>\n\n{prompt}"

        # Stateful Handover: если стартует чистая сессия и есть сохранённое резюме, инжектируем его
        if not conversation_id and context_summary:
            effective_prompt = (
                f"<previous_context_summary>\n"
                f"Это сжатое резюме предыдущей сессии в этом проекте (Stateful Handover). "
                f"Учитывай его как исходный контекст проекта и текущих договорённостей:\n\n"
                f"{context_summary}\n"
                f"</previous_context_summary>\n\n"
                f"{effective_prompt}"
            )

        cmd = [
            AGY_CLI_PATH,
            "--add-dir", str(project_dir),
            "-p", effective_prompt,
            "--effort", clean_effort,
            "--output-format", "text"
        ]

        if force_override:
            cmd.append("--dangerously-skip-permissions")

        if conversation_id:
            cmd.extend(["--conversation", conversation_id])

        if model_name:
            if "3.8" in model_name:
                cmd.extend(["--model", "gemini-3.8-flash"])
            elif "3.7" in model_name:
                cmd.extend(["--model", "gemini-3.7-flash"])
            elif "3.1" in model_name or "pro" in model_name.lower():
                cmd.extend(["--model", "gemini-3.1-pro"])
            elif "claude" in model_name.lower():
                cmd.extend(["--model", model_name])
            elif "flash" in model_name.lower():
                cmd.extend(["--model", "gemini-3.8-flash"])

        process = None
        try:
            async with temporary_deny_override(force_override):
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(project_dir),
                    start_new_session=True,
                    env=get_subprocess_env()
                )
                self._active_agents[user_id] = process

                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                has_output = False

                # Читаем вывод с защитой от зависания при незакрытых пайпах дочерних процессов
                while True:
                    if process.returncode is not None:
                        try:
                            chunk = await asyncio.wait_for(process.stdout.read(512), timeout=0.3)
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            break
                        if not chunk:
                            break
                        decoded = decoder.decode(chunk, final=False)
                        if decoded:
                            has_output = True
                            yield EngineEvent(event_type="token", content=decoded)
                        continue

                    read_task = asyncio.create_task(process.stdout.read(512))
                    wait_task = asyncio.create_task(process.wait())

                    try:
                        done, pending = await asyncio.wait(
                            [read_task, wait_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        if read_task in done:
                            for p in pending:
                                p.cancel()
                            chunk = read_task.result()
                            if not chunk:
                                break
                            decoded = decoder.decode(chunk, final=False)
                            if decoded:
                                has_output = True
                                yield EngineEvent(event_type="token", content=decoded)
                        else:
                            try:
                                chunk = await asyncio.wait_for(read_task, timeout=0.5)
                                if chunk:
                                    decoded = decoder.decode(chunk, final=False)
                                    if decoded:
                                        has_output = True
                                        yield EngineEvent(event_type="token", content=decoded)
                            except (asyncio.TimeoutError, asyncio.CancelledError):
                                read_task.cancel()
                            break

                    except asyncio.CancelledError:
                        read_task.cancel()
                        wait_task.cancel()
                        break

                final_tail = decoder.decode(b"", final=True)
                if final_tail:
                    has_output = True
                    yield EngineEvent(event_type="token", content=final_tail)

                try:
                    if process.returncode is None:
                        await asyncio.wait_for(process.wait(), timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass

                if not has_output and (process.returncode is not None and process.returncode != 0):
                    try:
                        err_bytes = await asyncio.wait_for(process.stderr.read(), timeout=1.0)
                        err_msg = err_bytes.decode(errors="replace").strip()
                        if err_msg:
                            logger.error(f"agy CLI завершился с кодом {process.returncode}: {err_msg}")
                            yield EngineEvent(event_type="error", content=err_msg)
                    except Exception:
                        pass

        except asyncio.CancelledError:
            logger.info(f"Стриминг CLI для user {user_id} был отменен.")
            if process:
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass
            raise

        finally:
            self._active_agents.pop(user_id, None)
            if process and process.returncode is None:
                try:
                    pgid = os.getpgid(process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    process.kill()
                except Exception:
                    pass

        new_id = get_latest_cli_conversation_id(known_ids_before)
        if new_id and new_id != conversation_id:
            yield EngineEvent(event_type="conversation_id", content=new_id)

    async def _stream_sdk_chat(
        self,
        user_id: int,
        prompt: str,
        project_dir: Path,
        model_name: Optional[str] = None
    ) -> AsyncGenerator[EngineEvent, None]:
        skills_paths = get_skills_paths()

        local_config = LocalAgentConfig(
            capabilities=CapabilitiesConfig(
                file_system=True,
                terminal=True,
                skills=skills_paths
            )
        )

        agent = Agent(local=local_config)
        self._active_agents[user_id] = agent

        bot_rules = get_bot_agent_rules()
        effective_prompt = prompt
        if bot_rules:
            effective_prompt = f"<system_invariants>\n{bot_rules}\n</system_invariants>\n\n{prompt}"

        try:
            generator = agent.stream_chat(prompt=effective_prompt)
            async for chunk in generator:
                yield EngineEvent(event_type="token", content=str(chunk))
        finally:
            self._active_agents.pop(user_id, None)


antigravity_bridge = AntigravityBridge()
