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
        bot.delete_message = AsyncMock()
        new_msg = MagicMock()
        new_msg.message_id = 1000
        bot.send_rich_message = AsyncMock(return_value=new_msg)
        streamer = LiveStreamer(bot=bot, chat_id=12345, reply_to_message_id=456)
        streamer.message_id = 999
        streamer.accumulated_text = "| A | B |\n| --- | --- |\n| 1 | 2 |"

        await streamer.finalize()

        bot.delete_message.assert_called_once_with(chat_id=12345, message_id=999)
        bot.send_rich_message.assert_called_once()
        call_kwargs = bot.send_rich_message.call_args.kwargs
        self.assertIn("rich_message", call_kwargs)
        self.assertIsInstance(call_kwargs["rich_message"], InputRichMessage)
        self.assertIn("| A | B |", call_kwargs["rich_message"].markdown)
        self.assertIsNotNone(call_kwargs.get("reply_parameters"))
        self.assertEqual(call_kwargs["reply_parameters"].message_id, 456)
        self.assertEqual(streamer.message_id, 1000)

    async def test_streamer_finalize_rich_message_fallback_to_edit(self):
        bot = MagicMock()
        # send_rich_message fails, falls back to edit_message_text with rich_message
        bot.send_rich_message = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="send_rich not allowed"))
        bot.edit_message_text = AsyncMock()
        bot.delete_message = AsyncMock()

        streamer = LiveStreamer(bot=bot, chat_id=12345)
        streamer.message_id = 999
        streamer.accumulated_text = "| A | B |\n| --- | --- |\n| 1 | 2 |"

        await streamer.finalize()

        bot.send_rich_message.assert_called_once()
        bot.edit_message_text.assert_called_once()
        call_kwargs = bot.edit_message_text.call_args.kwargs
        self.assertIn("rich_message", call_kwargs)
        self.assertIsInstance(call_kwargs["rich_message"], InputRichMessage)
        self.assertEqual(call_kwargs.get("message_id"), 999)
        bot.delete_message.assert_not_called()

    async def test_streamer_finalize_rich_message_fallback_to_card_html(self):
        bot = MagicMock()
        bot.delete_message = AsyncMock()
        bot.send_rich_message = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="Not supported"))
        bot.edit_message_text = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="Cannot edit"))
        new_msg = MagicMock()
        new_msg.message_id = 1001
        bot.send_message = AsyncMock(return_value=new_msg)

        streamer = LiveStreamer(bot=bot, chat_id=12345)
        streamer.message_id = 999
        streamer.accumulated_text = "| A | B |\n| --- | --- |\n| 1 | 2 |"

        await streamer.finalize()

        bot.send_rich_message.assert_called_once()
        bot.edit_message_text.assert_called_once()
        bot.delete_message.assert_called_once_with(chat_id=12345, message_id=999)
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args.kwargs
        self.assertEqual(call_kwargs.get("parse_mode"), "HTML")
        self.assertIn("<blockquote>", call_kwargs.get("text"))
        self.assertEqual(streamer.message_id, 1001)


if __name__ == "__main__":
    unittest.main()
