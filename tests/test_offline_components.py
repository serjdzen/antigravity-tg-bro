import unittest
from src.bot.locales import t
from src.bot.utils.formatter import (
    format_thought_block,
    format_tool_call_block,
    format_markdown_to_telegram_html,
    split_message
)
from src.bot.utils.streamer import close_unclosed_html_tags
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


if __name__ == "__main__":
    unittest.main()
