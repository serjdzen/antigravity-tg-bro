import html
import re
from typing import Any, Dict, List
from src.bot.locales import t


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def split_table_row(line: str) -> List[str]:
    parts = [p.strip() for p in line.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def is_table_delimiter_row(line: str) -> bool:
    s = line.strip()
    if not s or "|" not in s:
        return False
    parts = split_table_row(s)
    if not parts:
        return False
    return all(bool(re.match(r"^:?-{1,}:?$", p)) for p in parts)


def has_markdown_table(text: str) -> bool:
    """
    Checks if text contains a valid Markdown/GFM table.
    """
    if not text or "|" not in text:
        return False
    lines = text.split("\n")
    for i in range(len(lines) - 1):
        if is_table_delimiter_row(lines[i + 1]) and "|" in lines[i]:
            return True
    return False


def _format_cell_content(cell: str) -> str:
    """
    Safely escapes HTML and formats basic inline styles (bold, italic, code, links) inside a table cell.
    """
    code_matches = []
    def save_incode(m):
        code_matches.append(f"<code>{escape_html(m.group(1))}</code>")
        return f"__CELL_INCODE_{len(code_matches)-1}__"

    c_sub = re.sub(r"`([^`\n]+)`", save_incode, cell)
    c_sub = escape_html(c_sub)
    c_sub = re.sub(r"\*\*([^\*\n]+)\*\*", r"<b>\1</b>", c_sub)
    c_sub = re.sub(r"~~([^~\n]+)~~", r"<s>\1</s>", c_sub)
    c_sub = re.sub(r"(?<!\w)\*([^\*\n]+)\*(?!\w)", r"<i>\1</i>", c_sub)
    c_sub = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", c_sub)
    c_sub = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', c_sub)

    for idx, incode in enumerate(code_matches):
        c_sub = c_sub.replace(f"__CELL_INCODE_{idx}__", incode)
    return c_sub.strip()


def convert_markdown_tables_to_cards(text: str) -> str:
    """
    Converts all Markdown tables in text into mobile-friendly HTML card blocks (<blockquote>).
    Prevents tables from collapsing/wrapping awkwardly on smartphone screens.
    """
    if not has_markdown_table(text):
        return text

    lines = text.split("\n")
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" in line and i + 1 < len(lines) and is_table_delimiter_row(lines[i + 1]):
            header_line = line
            i += 2
            data_lines = []
            while i < len(lines) and "|" in lines[i] and not is_table_delimiter_row(lines[i]):
                data_lines.append(lines[i])
                i += 1

            headers = [_format_cell_content(h) for h in split_table_row(header_line)]
            cards = []
            for row_str in data_lines:
                cells = [_format_cell_content(c) for c in split_table_row(row_str)]
                if not cells or all(c == "" for c in cells):
                    continue
                row_lines = []
                if len(headers) == 2 and len(cells) >= 2:
                    title = cells[0]
                    val = cells[1]
                    h2 = headers[1] if len(headers) > 1 else ""
                    row_lines.append(f"<b>📌 {title}</b>")
                    if h2:
                        row_lines.append(f"↳ <i>{h2}:</i> {val}")
                    else:
                        row_lines.append(f"↳ {val}")
                else:
                    title = cells[0] if cells else ""
                    row_lines.append(f"<b>📌 {title}</b>")
                    for col_idx in range(1, len(cells)):
                        h_name = headers[col_idx] if col_idx < len(headers) else f"Колонка {col_idx+1}"
                        row_lines.append(f"• <b>{h_name}:</b> {cells[col_idx]}")
                card_html = "\n".join(row_lines)
                cards.append(f"<blockquote>{card_html}</blockquote>")

            if cards:
                output.append("\n\n".join(cards))
        else:
            output.append(line)
            i += 1

    return "\n".join(output)


def format_markdown_to_telegram_html(text: str, convert_tables: bool = True) -> str:
    """
    Converts standard Markdown (headers, bold, italic, lists, links, code, tables) into valid Telegram HTML.
    If convert_tables=True, Markdown tables are transformed into responsive Card Layout blocks.
    """
    if not text:
        return ""

    # 1. Multi-line code blocks ```lang\ncode\n```
    code_blocks = []
    def save_code_block(match):
        code = match.group(2)
        escaped_code = html.escape(code.strip(), quote=False)
        placeholder = f"__CODE_BLOCK_{len(code_blocks)}__"
        code_blocks.append(f"<pre>{escaped_code}</pre>")
        return placeholder

    pattern_multiline = r"```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```"
    text = re.sub(pattern_multiline, save_code_block, text)

    # 2. Inline code `code`
    inline_codes = []
    def save_inline_code(match):
        code = match.group(1)
        escaped_code = html.escape(code, quote=False)
        placeholder = f"__INLINE_CODE_{len(inline_codes)}__"
        inline_codes.append(f"<code>{escaped_code}</code>")
        return placeholder

    text = re.sub(r"`([^`\n]+)`", save_inline_code, text)

    # 3. Tables to Card Layout placeholders (if enabled)
    table_cards = []
    if convert_tables and has_markdown_table(text):
        lines = text.split("\n")
        rebuilt = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if "|" in line and i + 1 < len(lines) and is_table_delimiter_row(lines[i + 1]):
                table_chunk_lines = [line, lines[i + 1]]
                i += 2
                while i < len(lines) and "|" in lines[i] and not is_table_delimiter_row(lines[i]):
                    table_chunk_lines.append(lines[i])
                    i += 1
                raw_table = "\n".join(table_chunk_lines)
                converted_cards = convert_markdown_tables_to_cards(raw_table)
                placeholder = f"__TABLE_CARD_{len(table_cards)}__"
                table_cards.append(converted_cards)
                rebuilt.append(placeholder)
            else:
                rebuilt.append(line)
                i += 1
        text = "\n".join(rebuilt)

    # 4. Escape all remaining HTML entities
    text = html.escape(text, quote=False)

    # 5. Markdown headers (#, ##, ###) -> <b>Header</b>
    text = re.sub(r"^(?:#{1,6})\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # 6. File & Web links
    text = re.sub(r"\[([^\]]+)\]\(file://[^\)]+\)", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', text)

    # 7. Formatting (bold, strikethrough, italic)
    text = re.sub(r"\*\*([^\*\n]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"~~([^~\n]+)~~", r"<s>\1</s>", text)
    text = re.sub(r"(?<!\w)\*([^\*\n]+)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", text)

    # 8. Lists & Separators
    text = re.sub(r"^[*-]\s+", r"• ", text, flags=re.MULTILINE)
    text = re.sub(r"^(-{3,}|\*{3,})$", r"───────────────", text, flags=re.MULTILINE)

    # 9. Restore placeholders
    for idx, card in enumerate(table_cards):
        text = text.replace(f"__TABLE_CARD_{idx}__", card)
    for idx, block in enumerate(code_blocks):
        text = text.replace(f"__CODE_BLOCK_{idx}__", block)
    for idx, incode in enumerate(inline_codes):
        text = text.replace(f"__INLINE_CODE_{idx}__", incode)

    return text


def format_thought_block(thought: str, lang: str = "en") -> str:
    clean_thought = escape_html(thought.strip())
    header = t("thought_block_header", lang)
    return f'<blockquote expandable>{header}\n<i>{clean_thought}</i></blockquote>'


def format_tool_call_block(tool_name: str, args: Dict[str, Any], lang: str = "en") -> str:
    escaped_name = escape_html(tool_name)
    args_str = ""
    if args:
        import json
        try:
            formatted_json = json.dumps(args, ensure_ascii=False, indent=2)
            args_str = f"\n<pre>{escape_html(formatted_json)}</pre>"
        except Exception:
            args_str = f"\n<code>{escape_html(str(args))}</code>"

    header = t("tool_call_header", lang)
    return f'<blockquote expandable>{header} <code>{escaped_name}</code>{args_str}</blockquote>'


def split_message(text: str, max_chars: int = 4000) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0

    for line in lines:
        if current_len + len(line) + 1 > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += len(line) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks
