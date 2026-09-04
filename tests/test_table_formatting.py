import unittest
from unittest.mock import AsyncMock, MagicMock
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputRichMessage
from src.bot.utils.formatter import (
    has_markdown_table,
    convert_markdown_tables_to_cards,
    format_markdown_to_telegram_html,
    split_table_row,
    is_table_delimiter_row
)
from src.bot.utils.streamer import LiveStreamer


class TestTableFormatting(unittest.IsolatedAsyncioTestCase):

    def test_has_markdown_table_detection(self):
        # 1. Valid GFM 2-column table
        table_2col = (
            "| Параметр | Значение |\n"
            "| :--- | :--- |\n"
            "| Режим | Full Auto |\n"
        )
        self.assertTrue(has_markdown_table(table_2col))

        # 2. Valid multi-column table without outer pipes
        table_no_outer = (
            "Col1 | Col2 | Col3\n"
            "--- | :---: | ---:\n"
            "Val1 | Val2 | Val3\n"
        )
        self.assertTrue(has_markdown_table(table_no_outer))

        # 3. Regular text with pipes (e.g. bash commands or separators)
        plain_text = "Run: cat file | grep foo | wc -l"
        self.assertFalse(has_markdown_table(plain_text))

        # 4. Empty or none
        self.assertFalse(has_markdown_table(""))
        self.assertFalse(has_markdown_table(None))

    def test_convert_markdown_tables_to_cards(self):
        sample_table = (
            "| Текущий check.md | Что даёт новый промпт |\n"
            "| :--- | :--- |\n"
            "| **Базовый вопрос** | *Принцип Поппера* и `RAT` |\n"
            "| Ограничение | Сканер скиллов |\n"
        )
        converted = convert_markdown_tables_to_cards(sample_table)
        self.assertIn("<blockquote>", converted)
        self.assertIn("<b>📌 <b>Базовый вопрос</b></b>", converted)
        self.assertIn("↳ <i>Что даёт новый промпт:</i> <i>Принцип Поппера</i> и <code>RAT</code>", converted)
        self.assertIn("<b>📌 Ограничение</b>", converted)

    def test_format_markdown_to_telegram_html_with_table(self):
        md_text = (
            "# Заголовок\n\n"
            "Текст перед таблицей.\n\n"
            "| Metric | Score |\n"
            "| --- | --- |\n"
            "| Speed | 100% |\n\n"
            "Текст после таблицы."
        )
        html_out = format_markdown_to_telegram_html(md_text, convert_tables=True)
        self.assertIn("<b>Заголовок</b>", html_out)
        self.assertIn("<blockquote>", html_out)
        self.assertIn("<b>📌 Speed</b>", html_out)
        self.assertIn("Текст после таблицы.", html_out)

    def test_input_rich_message_serialization(self):
        table_md = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        rich_msg = InputRichMessage(markdown=table_md)
        dump = rich_msg.model_dump(exclude_none=True)
        self.assertEqual(dump.get("markdown"), table_md)

    async def test_streamer_finalize_rich_message_success(self):
        bot = MagicMock()
        bot.edit_message_text = AsyncMock()
        streamer = LiveStreamer(bot=bot, chat_id=12345)
        streamer.message_id = 999
        streamer.accumulated_text = "| A | B |\n| --- | --- |\n| 1 | 2 |"

        await streamer.finalize()

        bot.edit_message_text.assert_called_once()
        call_kwargs = bot.edit_message_text.call_args.kwargs
        self.assertIn("rich_message", call_kwargs)
        self.assertIsInstance(call_kwargs["rich_message"], InputRichMessage)
        self.assertIn("| A | B |", call_kwargs["rich_message"].markdown)

    async def test_streamer_finalize_rich_message_fallback_to_send(self):
        bot = MagicMock()
        # edit fails with BadRequest (e.g. converting regular to rich disallowed)
        bot.edit_message_text = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="Cannot convert"))
        bot.delete_message = AsyncMock()
        new_msg = MagicMock()
        new_msg.message_id = 1000
        bot.send_rich_message = AsyncMock(return_value=new_msg)

        streamer = LiveStreamer(bot=bot, chat_id=12345)
        streamer.message_id = 999
        streamer.accumulated_text = "| A | B |\n| --- | --- |\n| 1 | 2 |"

        await streamer.finalize()

        bot.edit_message_text.assert_called_once()
        bot.delete_message.assert_called_once_with(chat_id=12345, message_id=999)
        bot.send_rich_message.assert_called_once()
        self.assertEqual(streamer.message_id, 1000)

    async def test_streamer_finalize_rich_message_full_fallback_to_card_html(self):
        bot = MagicMock()
        # Both rich message attempts fail
        bot.edit_message_text = AsyncMock(side_effect=[
            TelegramBadRequest(method=MagicMock(), message="Cannot convert"),
            MagicMock() # Second call (Card Layout HTML fallback edit)
        ])
        bot.delete_message = AsyncMock()
        bot.send_rich_message = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="Not supported"))

        streamer = LiveStreamer(bot=bot, chat_id=12345)
        streamer.message_id = 999
        streamer.accumulated_text = "| A | B |\n| --- | --- |\n| 1 | 2 |"

        await streamer.finalize()

        # Should fall back to regular HTML edit with Card Layout
        self.assertEqual(bot.edit_message_text.call_count, 2)
        second_call = bot.edit_message_text.call_args_list[1].kwargs
        self.assertEqual(second_call.get("parse_mode"), "HTML")
        self.assertIn("<blockquote>", second_call.get("text"))


if __name__ == "__main__":
    unittest.main()
