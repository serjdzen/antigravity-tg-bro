import unittest
from src.bot.utils.formatter import (
    format_thought_block,
    format_tool_call_block,
    format_markdown_to_telegram_html,
    split_message
)
from src.config import Settings


class TestOfflineComponents(unittest.TestCase):

    def test_settings_allowed_ids(self):
        s = Settings(ALLOWED_USER_IDS="111, 222, 333", BOT_TOKEN="fake_token")
        self.assertEqual(s.allowed_ids_set, {111, 222, 333})

    def test_markdown_formatting_blocks(self):
        thought_html = format_thought_block("Thinking about step 1")
        self.assertIn("<blockquote expandable>", thought_html)
        self.assertIn("Thinking about step 1", thought_html)

        tool_html = format_tool_call_block("run_command", {"command": "ls -la"})
        self.assertIn("🛠️ <b>Вызов инструмента:</b> <code>run_command</code>", tool_html)
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


if __name__ == "__main__":
    unittest.main()
