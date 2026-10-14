import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.bot.locales import t
from src.bot.utils.formatter import (
    format_thought_block,
    format_tool_call_block,
    format_markdown_to_telegram_html,
    split_message
)
from src.bot.utils.streamer import close_unclosed_html_tags, LiveStreamer
from src.engine.models_loader import FEATURED_MODELS, get_model_emoji
from src.config import Settings
from src.engine.session_manager import UserSession
from src.bot.keyboards.settings_kb import build_system_settings_keyboard
from src.bot.handlers.settings import format_system_settings_text
from src.bot.handlers.chat import _get_user_queue, QueuedPrompt, MAX_QUEUE_SIZE


class TestOfflineComponents(unittest.TestCase):

    def test_settings_allowed_ids(self):
        s = Settings(ALLOWED_USER_IDS="111, 222, 333", BOT_TOKEN="fake_token", BOT_LANGUAGE="en")
        self.assertEqual(s.allowed_ids_set, {111, 222, 333})
        self.assertEqual(s.BOT_LANGUAGE, "en")

    def test_locales_resolution(self):
        en_welcome = t("start_welcome", "en")
        ru_welcome = t("start_welcome", "ru")
        self.assertIn("Welcome to Antigravity", en_welcome)
        self.assertIn("Добро пожаловать", ru_welcome)

        # Fallback test
        missing = t("non_existent_key", "en")
        self.assertEqual(missing, "[non_existent_key]")

    def test_markdown_formatting_blocks(self):
        thought_en = format_thought_block("Thinking about step 1", lang="en")
        self.assertIn("<blockquote expandable>", thought_en)
        self.assertIn("Agent Thoughts:", thought_en)

        thought_ru = format_thought_block("Думаю о шаге 1", lang="ru")
        self.assertIn("Мысли агента:", thought_ru)

        tool_html = format_tool_call_block("run_command", {"command": "ls -la"}, lang="en")
        self.assertIn("Tool Call:", tool_html)
        self.assertIn("ls -la", tool_html)

    def test_markdown_to_telegram_html(self):
        md = "# Header\n**Bold Text** and `code`"
        html_out = format_markdown_to_telegram_html(md)
        self.assertIn("<b>Header</b>", html_out)
        self.assertIn("<b>Bold Text</b>", html_out)
        self.assertIn("<code>code</code>", html_out)

    def test_split_message(self):
        short_text = "Hello world"
        parts = split_message(short_text, max_chars=100)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], short_text)

        long_text = "Line\n" * 1000
        parts = split_message(long_text, max_chars=500)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 500)

    def test_close_unclosed_html_tags(self):
        # 1. Simple unclosed bold
        raw = "Hello <b>World and some more text"
        safe = close_unclosed_html_tags(raw)
        self.assertEqual(safe, "Hello <b>World and some more text</b>")

        # 2. Nested unclosed tags
        raw2 = "<blockquote><b>Title</b>\n<code>let x = 1;"
        safe2 = close_unclosed_html_tags(raw2)
        self.assertEqual(safe2, "<blockquote><b>Title</b>\n<code>let x = 1;</code></blockquote>")

        # 3. Truncated mid-tag like "<blo"
        raw3 = "Some text <blo"
        safe3 = close_unclosed_html_tags(raw3)
        self.assertEqual(safe3, "Some text ")

    def test_featured_models_gemini_38(self):
        model_ids = [m[0] for m in FEATURED_MODELS]
        self.assertIn("gemini-3.8-flash", model_ids)
        self.assertEqual(get_model_emoji("gemini-3.8-flash"), "⚡")
        self.assertEqual(get_model_emoji("gemini-3.8-flash-high"), "⚡")

    def test_session_queue_mode(self):
        s = UserSession(user_id=99999)
        self.assertEqual(s.queue_mode, "queue")
        s.queue_mode = "block"
        self.assertEqual(s.queue_mode, "block")

    def test_system_settings_keyboard_queue_toggle(self):
        kb_queue = build_system_settings_keyboard(
            safety_approval=True,
            engine_mode="cli",
            queue_mode="queue",
            lang="en"
        )
        buttons = [b for row in kb_queue.inline_keyboard for b in row]
        queue_btn = next((b for b in buttons if b.callback_data == "toggle_queue"), None)
        self.assertIsNotNone(queue_btn)
        self.assertIn("ON (Queue)", queue_btn.text)

        kb_block = build_system_settings_keyboard(
            safety_approval=True,
            engine_mode="cli",
            queue_mode="block",
            lang="ru"
        )
        buttons_block = [b for row in kb_block.inline_keyboard for b in row]
        queue_btn_block = next((b for b in buttons_block if b.callback_data == "toggle_queue"), None)
        self.assertIsNotNone(queue_btn_block)
        self.assertIn("ВЫКЛ (Block)", queue_btn_block.text)

    def test_system_settings_text_queue(self):
        text_queue_en = format_system_settings_text(
            safety_approval=True,
            engine_mode="cli",
            queue_mode="queue",
            lang="en"
        )
        self.assertIn("Message Queue:", text_queue_en)
        self.assertIn("ENABLED (Queue)", text_queue_en)

        text_block_ru = format_system_settings_text(
            safety_approval=True,
            engine_mode="cli",
            queue_mode="block",
            lang="ru"
        )
        self.assertIn("Очередь сообщений:", text_block_ru)
        self.assertIn("ВЫКЛЮЧЕНА (Block)", text_block_ru)

    def test_user_queue_operations(self):
        test_uid = 88888
        q = _get_user_queue(test_uid)
        self.assertEqual(q.qsize(), 0)
        item = QueuedPrompt(
            chat_id=123,
            user_id=test_uid,
            bot=None,  # type: ignore
            prompt_text="Test prompt"
        )
        q.put_nowait(item)
        self.assertEqual(q.qsize(), 1)
        popped = q.get_nowait()
        self.assertEqual(popped.prompt_text, "Test prompt")
        self.assertEqual(q.qsize(), 0)

    def test_streamer_with_existing_message_id(self):
        """Verify LiveStreamer reuses existing_message_id without sending a duplicate start message."""
        async def _run():
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock()
            mock_bot.delete_message = AsyncMock()

            streamer = LiveStreamer(
                bot=mock_bot,
                chat_id=123,
                reply_to_message_id=456,
                existing_message_id=789
            )

            # start() should NOT send a new message
            await streamer.start()
            mock_bot.send_message.assert_not_called()
            self.assertEqual(streamer.message_id, 789)

            # finalize() should delete the existing message and send a fresh response
            streamer.accumulated_text = "Hello world"
            new_sent = MagicMock()
            new_sent.message_id = 999
            mock_bot.send_message.return_value = new_sent

            await streamer.finalize()
            mock_bot.delete_message.assert_called_once_with(chat_id=123, message_id=789)
            mock_bot.send_message.assert_called_once()
            self.assertEqual(streamer.message_id, 999)

        asyncio.run(_run())

    def test_streamer_multi_chunk_delivery(self):
        """Verify LiveStreamer splits large messages (>3900 chars), deletes placeholder once, and sets reply_markup on last chunk."""
        async def _run():
            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock()
            mock_bot.delete_message = AsyncMock()

            streamer = LiveStreamer(
                bot=mock_bot,
                chat_id=123,
                reply_to_message_id=456,
                existing_message_id=789
            )

            # Generate long text that splits into 2 chunks
            long_para1 = "A" * 3000
            long_para2 = "B" * 3000
            streamer.accumulated_text = f"{long_para1}\n\n{long_para2}"

            dummy_kb = MagicMock()
            await streamer.finalize(reply_markup=dummy_kb)

            # Placeholder must be deleted exactly once
            mock_bot.delete_message.assert_called_once_with(chat_id=123, message_id=789)

            # Must have sent at least 2 chunks
            self.assertGreaterEqual(mock_bot.send_message.call_count, 2)

            # First chunk must reply to reply_to_message_id (456)
            first_call_kwargs = mock_bot.send_message.call_args_list[0].kwargs
            self.assertEqual(first_call_kwargs.get("reply_to_message_id"), 456)
            self.assertIsNone(first_call_kwargs.get("reply_markup"))

            # Last chunk must have the reply_markup and no reply_to_message_id
            last_call_kwargs = mock_bot.send_message.call_args_list[-1].kwargs
            self.assertEqual(last_call_kwargs.get("reply_markup"), dummy_kb)
            self.assertIsNone(last_call_kwargs.get("reply_to_message_id"))

        asyncio.run(_run())

    def test_handle_voice_message_seamless_transition(self):
        """Verify handle_voice_message in-place edits status_msg to 'Генерирую ответ...' and passes existing_message_id."""
        async def _run():
            from unittest.mock import patch
            from src.bot.handlers.chat import handle_voice_message
            from src.engine.voice_transcriber import voice_transcriber

            mock_bot = AsyncMock()
            mock_bot.download = AsyncMock()

            mock_status_msg = AsyncMock()
            mock_status_msg.message_id = 555
            mock_status_msg.edit_text = AsyncMock()

            mock_msg = AsyncMock()
            mock_msg.voice = MagicMock()
            mock_msg.voice.file_id = "voice_file_123"
            mock_msg.from_user = MagicMock()
            mock_msg.from_user.id = 12345
            mock_msg.chat = MagicMock()
            mock_msg.chat.id = 67890
            mock_msg.message_id = 111
            mock_msg.reply = AsyncMock(return_value=mock_status_msg)

            with patch.object(voice_transcriber, "api_key", "dummy_groq_key"), \
                 patch("src.bot.handlers.chat.voice_transcriber.transcribe_audio_bytes", AsyncMock(return_value="Протестируй бота")), \
                 patch("src.bot.handlers.chat._execute_prompt", AsyncMock()) as mock_exec:

                await handle_voice_message(mock_msg, mock_bot)

                # 1. Sent initial "Расшифровываю голос..."
                mock_msg.reply.assert_called_once()

                # 2. In-place edited into "Генерирую ответ..."
                mock_status_msg.edit_text.assert_called_once()
                edit_call_args = mock_status_msg.edit_text.call_args
                self.assertIn("Генерирую ответ...", edit_call_args[0][0])

                # 3. Passed existing_message_id=555 to _execute_prompt
                mock_exec.assert_called_once()
                exec_kwargs = mock_exec.call_args.kwargs
                self.assertEqual(exec_kwargs.get("existing_message_id"), 555)
                self.assertEqual(exec_kwargs.get("prompt_text"), "Протестируй бота")
                self.assertEqual(exec_kwargs.get("reply_to_message_id"), 111)

    def test_get_subprocess_env_injects_system_proxies(self):
        """Verify get_subprocess_env dynamically discovers and normalizes macOS system proxies."""
        from unittest.mock import patch
        from src.engine.antigravity_bridge import get_subprocess_env

        mock_proxies = {
            "https": "http://127.0.0.1:51367",
            "http": "127.0.0.1:51367"
        }

        with patch("urllib.request.getproxies", return_value=mock_proxies):
            env = get_subprocess_env()
            self.assertEqual(env.get("HTTPS_PROXY"), "http://127.0.0.1:51367")
            self.assertEqual(env.get("https_proxy"), "http://127.0.0.1:51367")
            # Should normalize missing schema to http://
            self.assertEqual(env.get("HTTP_PROXY"), "http://127.0.0.1:51367")
            self.assertEqual(env.get("http_proxy"), "http://127.0.0.1:51367")


if __name__ == "__main__":
    unittest.main()
