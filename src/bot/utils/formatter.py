import html
import re
from typing import Any, Dict, List
from src.bot.locales import t


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def format_markdown_to_telegram_html(text: str) -> str:
    """
    Converts standard Markdown (headers, bold, italic, lists, links, code) into valid Telegram HTML.
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

    # 3. Escape all remaining HTML entities
    text = html.escape(text, quote=False)

    # 4. Markdown headers (#, ##, ###) -> <b>Header</b>
    text = re.sub(r"^(?:#{1,6})\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # 5. File & Web links
    text = re.sub(r"\[([^\]]+)\]\(file://[^\)]+\)", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', text)

    # 6. Formatting (bold, strikethrough, italic)
    text = re.sub(r"\*\*([^\*\n]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"~~([^~\n]+)~~", r"<s>\1</s>", text)
    text = re.sub(r"(?<!\w)\*([^\*\n]+)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", text)

    # 7. Lists & Separators
    text = re.sub(r"^[*-]\s+", r"• ", text, flags=re.MULTILINE)
    text = re.sub(r"^(-{3,}|\*{3,})$", r"───────────────", text, flags=re.MULTILINE)

    # 8. Restore code placeholders
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
