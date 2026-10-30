import io
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from aiogram.exceptions import TelegramNetworkError
import aiohttp

from src.bot.handlers.chat import (
    _download_media_with_retry,
    _execute_single_prompt,
    QueuedPrompt,
    BASE_TURN_TIMEOUT_SECONDS,
    WATCHDOG_EXTENSION_SECONDS,
    MAX_WATCHDOG_EXTENSIONS
)
from src.engine.antigravity_bridge import antigravity_bridge, EngineEvent
from src.engine.session_manager import session_manager


class TestAdaptiveWatchdogAndRetries(unittest.IsolatedAsyncioTestCase):

    async def test_download_media_success_first_try(self):
        bot = MagicMock()
        bot.download = AsyncMock(return_value=True)
        buf = io.BytesIO()

        ok = await _download_media_with_retry(bot, "file_123", buf, max_attempts=3, timeout_per_try=1.0)
        self.assertTrue(ok)
        self.assertEqual(bot.download.call_count, 1)

    async def test_download_media_success_after_transient_failure(self):
        bot = MagicMock()
        # Fail first time with TelegramNetworkError, succeed second time
        bot.download = AsyncMock(side_effect=[
            TelegramNetworkError(message="Connection reset by peer", method="getFile"),
            True
        ])
        buf = io.BytesIO()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            ok = await _download_media_with_retry(bot, "file_123", buf, max_attempts=3, timeout_per_try=1.0)
            self.assertTrue(ok)
            self.assertEqual(bot.download.call_count, 2)
            mock_sleep.assert_awaited_once_with(2.0)

    async def test_download_media_fails_on_non_transient_error(self):
        bot = MagicMock()
        bot.download = AsyncMock(side_effect=ValueError("Invalid file ID format"))
        buf = io.BytesIO()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            ok = await _download_media_with_retry(bot, "file_invalid", buf, max_attempts=3, timeout_per_try=1.0)
            self.assertFalse(ok)
            self.assertEqual(bot.download.call_count, 1)
            mock_sleep.assert_not_called()

    async def test_download_media_exhausts_max_retries(self):
        bot = MagicMock()
        bot.download = AsyncMock(side_effect=asyncio.TimeoutError())
        buf = io.BytesIO()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            ok = await _download_media_with_retry(bot, "file_123", buf, max_attempts=3, timeout_per_try=0.1)
            self.assertFalse(ok)
            self.assertEqual(bot.download.call_count, 3)
            self.assertEqual(mock_sleep.await_count, 2)

    async def test_is_agent_alive_detection(self):
        user_id = 99999
        self.assertFalse(antigravity_bridge.is_agent_alive(user_id))

        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.pid = 12345
        antigravity_bridge._active_agents[user_id] = mock_proc

        with patch("os.kill", return_value=None):
            self.assertTrue(antigravity_bridge.is_agent_alive(user_id))

        # When process has exited (ProcessLookupError)
        with patch("os.kill", side_effect=ProcessLookupError):
            self.assertFalse(antigravity_bridge.is_agent_alive(user_id))

        # Cleanup
        antigravity_bridge._active_agents.pop(user_id, None)

    async def test_adaptive_watchdog_extends_timeout_when_agent_alive(self):
        user_id = 88888
        chat_id = 88888
        session = session_manager.get_session(user_id)
        session.language = "ru"

        bot = MagicMock()
        bot.delete_message = AsyncMock()

        # Mock LiveStreamer
        with patch("src.bot.handlers.chat.LiveStreamer") as MockStreamer:
            streamer_instance = MagicMock()
            streamer_instance.start = AsyncMock()
            streamer_instance.update_text = AsyncMock()
            streamer_instance.update_status = AsyncMock()
            streamer_instance.finalize = AsyncMock()
            MockStreamer.return_value = streamer_instance

            # We simulate stream_chat that sleeps longer than base slice
            async def mock_stream_chat(*args, **kwargs):
                await asyncio.sleep(0.15)
                yield EngineEvent(event_type="token", content="Hello after lag")

            with patch.object(antigravity_bridge, "stream_chat", side_effect=mock_stream_chat), \
                 patch.object(antigravity_bridge, "is_agent_alive", return_value=True), \
                 patch("src.bot.handlers.chat.BASE_TURN_TIMEOUT_SECONDS", 0.05), \
                 patch("src.bot.handlers.chat.WATCHDOG_EXTENSION_SECONDS", 0.15), \
                 patch("src.bot.handlers.chat.MAX_WATCHDOG_EXTENSIONS", 2):

                item = QueuedPrompt(
                    chat_id=chat_id,
                    user_id=user_id,
                    bot=bot,
                    prompt_text="test lag",
                    reply_to_message_id=None
                )
                await _execute_single_prompt(item)

                # streamer.update_status should have been called when watchdog extended!
                self.assertTrue(streamer_instance.update_status.called)
                status_call_arg = streamer_instance.update_status.call_args[0][0]
                self.assertIn("Ожидание ответа затягивается", status_call_arg)
                # streamer.finalize should have received the completed token
                self.assertTrue(streamer_instance.finalize.called)

    async def test_adaptive_watchdog_kills_after_max_extensions(self):
        user_id = 77777
        chat_id = 77777
        session = session_manager.get_session(user_id)
        session.language = "ru"

        bot = MagicMock()
        bot.delete_message = AsyncMock()

        with patch("src.bot.handlers.chat.LiveStreamer") as MockStreamer:
            streamer_instance = MagicMock()
            streamer_instance.start = AsyncMock()
            streamer_instance.update_text = AsyncMock()
            streamer_instance.update_status = AsyncMock()
            streamer_instance.finalize = AsyncMock()
            MockStreamer.return_value = streamer_instance

            # Hanging forever stream
            async def hanging_stream(*args, **kwargs):
                while True:
                    await asyncio.sleep(1)
                    yield EngineEvent(event_type="thought", content="thinking...")

            with patch.object(antigravity_bridge, "stream_chat", side_effect=hanging_stream), \
                 patch.object(antigravity_bridge, "is_agent_alive", return_value=True), \
                 patch.object(antigravity_bridge, "cancel_active_task", return_value=True) as mock_cancel, \
                 patch("src.bot.handlers.chat.BASE_TURN_TIMEOUT_SECONDS", 0.02), \
                 patch("src.bot.handlers.chat.WATCHDOG_EXTENSION_SECONDS", 0.02), \
                 patch("src.bot.handlers.chat.MAX_WATCHDOG_EXTENSIONS", 2):

                item = QueuedPrompt(
                    chat_id=chat_id,
                    user_id=user_id,
                    bot=bot,
                    prompt_text="test hang",
                    reply_to_message_id=None
                )
                await _execute_single_prompt(item)

                # Check that cancel_active_task was called when max extensions were exceeded
                mock_cancel.assert_called_once_with(user_id)
                self.assertEqual(streamer_instance.update_status.call_count, 2)
                self.assertTrue(streamer_instance.finalize.called)
                extra_blocks = streamer_instance.finalize.call_args[1].get("extra_blocks", [])
                timeout_block = [b for b in extra_blocks if "таймаут" in b or "Превышен" in b]
                self.assertTrue(len(timeout_block) > 0)


if __name__ == "__main__":
    unittest.main()
