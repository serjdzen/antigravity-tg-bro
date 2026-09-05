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


if __name__ == "__main__":
    unittest.main()
