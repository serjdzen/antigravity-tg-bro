import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from aiogram.types import Message, User, Chat, BotCommand

from src.bot.utils.streamer import LiveStreamer
from src.bot.handlers.chat import handle_compact_command
from src.engine.session_manager import session_manager, UserSession
from src.engine.antigravity_bridge import antigravity_bridge
from src.bot.locales import t


class TestCompactAndMonitoring(unittest.IsolatedAsyncioTestCase):

    async def test_streamer_empty_output_shows_honest_warning_not_stub(self):
        """Verify streamer outputs an honest warning when agent returns empty text, NOT 'Задача выполнена'."""
        mock_bot = AsyncMock()
        mock_bot.edit_message_text = AsyncMock()
        mock_bot.delete_message = AsyncMock()

        streamer = LiveStreamer(
            bot=mock_bot,
            chat_id=12345,
        )
        streamer.message_id = 999
        streamer.accumulated_text = ""

        await streamer.finalize(extra_blocks=[])

        mock_bot.delete_message.assert_called_once_with(chat_id=12345, message_id=999)
        mock_bot.send_message.assert_called_once()
        called_args, called_kwargs = mock_bot.send_message.call_args
        sent_text = called_kwargs.get("text", "")

        self.assertNotIn("✅ Задача выполнена", sent_text)
        self.assertIn("Ответ от агента пуст или был прерван", sent_text)

    async def test_handle_compact_command_resets_conversation(self):
        """Verify /compact resets agy_conversation_id and message counter, and archives session with summary."""
        test_uid = 987654321
        session = session_manager.get_session(test_uid)
        active_chat = session.get_active_chat()
        active_chat.agy_conversation_id = "test-conv-uuid-12345"
        active_chat.messages_count = 42

        mock_user = MagicMock(spec=User)
        mock_user.id = test_uid
        mock_chat = MagicMock(spec=Chat)
        mock_chat.id = test_uid

        mock_status_msg = AsyncMock(spec=Message)
        mock_status_msg.edit_text = AsyncMock()

        mock_message = AsyncMock(spec=Message)
        mock_message.text = "/compact"
        mock_message.from_user = mock_user
        mock_message.chat = mock_chat
        mock_message.reply = AsyncMock(return_value=mock_status_msg)

        mock_bot = AsyncMock()

        dummy_summary = "### 🎯 Активная цель\nТестирование функционала\n### 📝 Принятые решения\nВсе тесты зелёные"

        with patch("src.bot.handlers.chat.antigravity_bridge.generate_conversation_summary", new=AsyncMock(return_value=dummy_summary)):
            await handle_compact_command(mock_message, mock_bot)

        # Assert conversation ID is cleared and message counter reset to 0
        self.assertIsNone(active_chat.agy_conversation_id)
        self.assertEqual(active_chat.messages_count, 0)
        self.assertEqual(active_chat.context_summary, dummy_summary)

        # Assert user got confirmation reply via status_msg.edit_text
        mock_status_msg.edit_text.assert_called_once()
        reply_text = mock_status_msg.edit_text.call_args[0][0]
        self.assertTrue(
            "сжат" in reply_text.lower() or "compressed" in reply_text.lower()
        )
        self.assertIn("test-con", reply_text)
        self.assertIn("Активная цель", reply_text)

    async def test_handle_compact_command_already_clean(self):
        """Verify /compact gracefully notifies when session is already clean."""
        test_uid = 987654322
        session = session_manager.get_session(test_uid)
        active_chat = session.get_active_chat()
        active_chat.agy_conversation_id = None
        active_chat.messages_count = 0

        mock_user = MagicMock(spec=User)
        mock_user.id = test_uid
        mock_chat = MagicMock(spec=Chat)
        mock_chat.id = test_uid

        mock_message = AsyncMock(spec=Message)
        mock_message.from_user = mock_user
        mock_message.chat = mock_chat
        mock_message.reply = AsyncMock()

        mock_bot = AsyncMock()

        await handle_compact_command(mock_message, mock_bot)

        self.assertIsNone(active_chat.agy_conversation_id)
        mock_message.reply.assert_called_once()
        reply_text = mock_message.reply.call_args[0][0]
        self.assertTrue(
            "чист" in reply_text.lower() or "clean" in reply_text.lower()
        )

    def test_locales_contain_compact_guidance(self):
        """Verify both Russian and English locales explain /compact."""
        for lang in ("ru", "en"):
            welcome = t("start_welcome", lang)
            help_doc = t("help_text", lang)
            self.assertIn("/compact", welcome)
            self.assertIn("/compact", help_doc)

    async def test_register_bot_commands_includes_compact(self):
        """Verify setup_bot_commands sets /compact in Telegram menu."""
        from main import setup_bot_commands
        mock_bot = AsyncMock()
        mock_bot.set_my_commands = AsyncMock()

        await setup_bot_commands(mock_bot)

        self.assertEqual(mock_bot.set_my_commands.call_count, 3)

        # Check en call
        en_cmds = mock_bot.set_my_commands.call_args_list[0][0][0]
        en_cmd_names = [c.command for c in en_cmds]
        self.assertIn("compact", en_cmd_names)

        # Check ru call
        ru_cmds = mock_bot.set_my_commands.call_args_list[2][0][0]
        ru_cmd_names = [c.command for c in ru_cmds]
        self.assertIn("compact", ru_cmd_names)

    async def test_stream_cli_chat_injects_previous_context_summary(self):
        """Verify new session prompt receives <previous_context_summary> when context_summary is present."""
        from src.engine.antigravity_bridge import antigravity_bridge
        from pathlib import Path

        dummy_summary = "### 🎯 Активная цель\nРазработка бота"
        captured_cmd = []

        async def fake_stream_cli(*args, **kwargs):
            # Check kwargs or args
            pass

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(return_value=b"")
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            gen = antigravity_bridge._stream_cli_chat(
                user_id=123,
                prompt="Привет, продолжим работу",
                project_dir=Path("/tmp"),
                conversation_id=None,
                context_summary=dummy_summary
            )
            async for _ in gen:
                pass

            self.assertTrue(mock_exec.called)
            called_args = mock_exec.call_args[0]
            # Find -p argument in called CLI command
            self.assertIn("-p", called_args)
            p_index = called_args.index("-p")
            passed_prompt = called_args[p_index + 1]
            self.assertIn("<previous_context_summary>", passed_prompt)
            self.assertIn(dummy_summary, passed_prompt)
            self.assertIn("Привет, продолжим работу", passed_prompt)

    async def test_generate_conversation_summary_success(self):
        """Test successful summary generation with clean output."""
        from pathlib import Path
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=("### 🎯 Summary text".encode("utf-8"), b""))
            mock_exec.return_value = mock_proc

            summary = await antigravity_bridge.generate_conversation_summary(
                conversation_id="test-cid-123",
                project_dir=Path("/tmp"),
                timeout_seconds=240
            )
            self.assertEqual(summary, "### 🎯 Summary text")
            self.assertTrue(mock_exec.called)

    async def test_generate_conversation_summary_timeout(self):
        """Test timeout during summary generation kills process and returns None."""
        from pathlib import Path
        with patch("asyncio.create_subprocess_exec") as mock_exec, \
             patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            mock_proc = AsyncMock()
            mock_proc.kill = unittest.mock.MagicMock()
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            summary = await antigravity_bridge.generate_conversation_summary(
                conversation_id="test-cid-timeout",
                project_dir=Path("/tmp"),
                timeout_seconds=5
            )
            self.assertIsNone(summary)
            mock_proc.kill.assert_called_once()
            mock_proc.wait.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
