import io
import re
import time
import logging
from urllib.parse import unquote
from pathlib import Path
from typing import Optional, List
from aiogram import Router, types, Bot, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from src.engine.session_manager import session_manager
from src.engine.antigravity_bridge import antigravity_bridge, EngineEvent
from src.engine.voice_transcriber import voice_transcriber
from src.engine.uploads_manager import ensure_uploads_dir
from src.bot.utils.formatter import format_thought_block, format_tool_call_block
from src.bot.utils.streamer import LiveStreamer

logger = logging.getLogger(__name__)
router = Router(name="chat_router")

# Текстовые расширения, требующие UTF-8 BOM для iOS QuickLook
TEXT_FILE_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".csv", ".json", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".astro", ".html",
    ".css", ".sh", ".env", ".log", ".sql", ".xml"
}


def prepare_attachment_file(file_path: Path):
    """
    Подготавливает файл для отправки в Telegram.
    Для текстовых форматов (Markdown, код, txt) добавляет UTF-8 BOM,
    чтобы iOS QuickLook на iPhone открывал кириллицу без кракозябр (mojibake).
    """
    ext = file_path.suffix.lower()
    if ext in TEXT_FILE_EXTENSIONS:
        try:
            raw_bytes = file_path.read_bytes()
            if not raw_bytes.startswith(b"\xef\xbb\xbf"):
                raw_bytes = b"\xef\xbb\xbf" + raw_bytes
            return BufferedInputFile(file=raw_bytes, filename=file_path.name)
        except Exception as e:
            logger.warning(f"Не удалось подготовить текстовый файл {file_path} с BOM: {e}")
    return FSInputFile(path=str(file_path), filename=file_path.name)


# Хранилище точного текста последнего запроса пользователя для разового переопределения
_LAST_USER_PROMPT = {}


def extract_attachment_paths(text: str) -> List[Path]:
    """
    Находит в выводе агента пути к файлам и изображениям, которые агент хотел отправить:
    - Markdown-картинки: ![alt](/path/to/file)
    - Ссылки на локальные файлы: [text](file:///path/to/file)
    """
    found_paths = []
    
    # 1. Markdown изображения: ![...](path)
    img_matches = re.findall(r'!\[.*?\]\(([^)]+)\)', text)
    for match in img_matches:
        clean_str = unquote(match.replace("file://", "").strip())
        p = Path(clean_str)
        if p.is_file() and p.exists() and p not in found_paths:
            found_paths.append(p)

    # 2. Файловые ссылки: [файл](file:///path)
    file_matches = re.findall(r'\[.*?\]\(file://([^)]+)\)', text)
    for match in file_matches:
        clean_str = unquote(match.strip())
        p = Path(clean_str)
        if p.is_file() and p.exists() and p not in found_paths:
            found_paths.append(p)

    return found_paths


async def _execute_prompt(
    chat_id: int,
    user_id: int,
    bot: Bot,
    prompt_text: str,
    reply_to_message_id: Optional[int] = None,
    force_override: bool = False
):
    session = session_manager.get_session(user_id)
    active_chat = session.get_active_chat()

    if session.lock.locked():
        await bot.send_message(
            chat_id=chat_id,
            text="⏳ <b>Агент уже выполняет предыдущую задачу.</b>\nПожалуйста, дождитесь завершения.",
            reply_to_message_id=reply_to_message_id,
            parse_mode="HTML"
        )
        return

    _LAST_USER_PROMPT[user_id] = prompt_text

    # Если в /settings выключена защита (safety_approval=False), то force_override автоматически активен
    effective_override = force_override or (not session.safety_approval)

    async with session.lock:
        streamer = LiveStreamer(bot=bot, chat_id=chat_id, reply_to_message_id=reply_to_message_id)
        await streamer.start()

        thought_blocks = []
        tool_blocks = []
        full_response_text = []

        if active_chat.messages_count == 0:
            clean_title = prompt_text[:30].replace("\n", " ").strip()
            active_chat.title = f"💬 {clean_title}..."

        active_chat.messages_count += 1
        active_chat.updated_at = time.time()

        try:
            async for event in antigravity_bridge.stream_chat(
                user_id=user_id,
                prompt=prompt_text,
                project_dir=session.current_project_dir,
                model_name=session.current_model,
                effort=session.reasoning_effort,
                conversation_id=active_chat.agy_conversation_id,
                engine_mode=session.engine_mode,
                force_override=effective_override
            ):
                if event.event_type == "conversation_id":
                    if event.content:
                        active_chat.agy_conversation_id = str(event.content)
                        session_manager.save_to_disk()
                elif event.event_type == "thought":
                    if event.content:
                        thought_blocks.append(format_thought_block(str(event.content)))
                elif event.event_type == "tool_call":
                    tool_info = event.content or {}
                    tool_name = tool_info.get("name", "tool")
                    tool_args = tool_info.get("args", {})
                    tool_blocks.append(format_tool_call_block(tool_name, tool_args))
                elif event.event_type == "token":
                    if event.content:
                        full_response_text.append(str(event.content))
                        await streamer.update_text(str(event.content))
                elif event.event_type == "error":
                    thought_blocks.append(f"⚠️ <b>Ошибка выполнения:</b>\n<code>{event.content}</code>")

        except Exception as e:
            logger.error(f"Необработанная ошибка в диалоге: {e}", exc_info=True)
            thought_blocks.append(f"❌ <b>Критическая ошибка агента:</b>\n<code>{str(e)}</code>")

        finally:
            extra_blocks = thought_blocks + tool_blocks
            complete_output = "".join(full_response_text)

            # Проверяем, была ли команда заблокирована политикой deny
            kb = None
            if session.safety_approval and not force_override:
                if ("Permission denied" in complete_output or "deny rule" in complete_output or "заблокирован" in complete_output.lower()):
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="⚡ Разрешить разово (Force Override)",
                                callback_data="force_execute"
                            )
                        ]
                    ])

            await streamer.finalize(extra_blocks=extra_blocks, reply_markup=kb)
            session_manager.save_to_disk()

            # 📤 АВТОМАТИЧЕСКАЯ ОТПРАВКА ФАЙЛОВ / КАРТИНОК ИЗ ОТВЕТА АГЕНТА:
            attachments = extract_attachment_paths(complete_output)
            for file_path in attachments:
                try:
                    file_size_mb = file_path.stat().st_size / (1024 * 1024)
                    if file_size_mb > 50:
                        logger.info(f"Файл {file_path.name} слишком большой ({file_size_mb:.1f} MB), пропуск.")
                        continue

                    ext = file_path.suffix.lower()
                    if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                        input_file = FSInputFile(path=str(file_path), filename=file_path.name)
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=input_file,
                            caption=f"🖼 <b>{file_path.name}</b>",
                            parse_mode="HTML"
                        )
                    else:
                        input_file = prepare_attachment_file(file_path)
                        await bot.send_document(
                            chat_id=chat_id,
                            document=input_file,
                            caption=f"📄 <b>{file_path.name}</b>",
                            parse_mode="HTML"
                        )
                    logger.info(f"📤 Автоматически отправлен файл пользователю: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Не удалось автоматически отправить файл {file_path}: {e}")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_chat_message(message: types.Message, bot: Bot):
    await _execute_prompt(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        bot=bot,
        prompt_text=message.text,
        reply_to_message_id=message.message_id,
        force_override=False
    )


@router.callback_query(F.data == "force_execute")
async def handle_force_execute_callback(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    last_prompt = _LAST_USER_PROMPT.get(user_id)

    if not last_prompt:
        await callback.answer("⚠️ Не удалось найти предыдущий запрос.", show_alert=True)
        return

    await callback.answer("⚡ Запуск с разовым снятием защиты (CLI --dangerously-skip-permissions)...")
    if callback.message:
        await _execute_prompt(
            chat_id=callback.message.chat.id,
            user_id=user_id,
            bot=bot,
            prompt_text=last_prompt,
            reply_to_message_id=callback.message.message_id,
            force_override=True
        )


@router.message(F.text == "/force")
async def handle_force_command(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    last_prompt = _LAST_USER_PROMPT.get(user_id)

    if not last_prompt:
        await message.reply("⚠️ Нет предыдущего запроса для повторного выполнения с пропуском защиты.")
        return

    await message.reply("⚡ <b>Повторный запуск с разовым снятием защиты...</b>", parse_mode="HTML")
    await _execute_prompt(
        chat_id=message.chat.id,
        user_id=user_id,
        bot=bot,
        prompt_text=last_prompt,
        reply_to_message_id=message.message_id,
        force_override=True
    )


@router.message(F.text == "/stop")
async def handle_stop_command(message: types.Message, bot: Bot):
    """
    Команда /stop:
    - Принудительно прерывает выполнение активной задачи агента.
    """
    user_id = message.from_user.id
    was_cancelled = antigravity_bridge.cancel_active_task(user_id)

    if was_cancelled:
        await message.reply("⏹ <b>Выполнение задачи принудительно остановлено.</b>", parse_mode="HTML")
    else:
        await message.reply("ℹ️ В данный момент нет активных задач для остановки.", parse_mode="HTML")


@router.message(F.voice | F.audio)
async def handle_voice_message(message: types.Message, bot: Bot):
    """
    Обработчик голосовых сообщений:
    - Загружает аудиофайл .ogg из Telegram.
    - Передает в Groq Whisper Large v3 Turbo для мгновенной транскрибации.
    - Направляет распознанный текст напрямую в Antigravity CLI.
    """
    if not voice_transcriber.is_configured:
        await message.reply(
            "🎙️ <b>Распознавание голосовых сообщений</b>\n\n"
            "⚠️ Для мгновенной расшифровки через <b>Groq Whisper Large v3 Turbo</b>, "
            "укажите ваш <code>GROQ_API_KEY</code> в файле <code>.env</code> проекта.\n\n"
            "🔑 Получить бесплатный ключ: <a href='https://console.groq.com/keys'>console.groq.com/keys</a>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    status_msg = await message.reply("🎙️ <i>Слушаю и расшифровываю голосовое сообщение...</i>", parse_mode="HTML")

    try:
        file_io = io.BytesIO()
        await bot.download(file=file_id, destination=file_io)
        audio_bytes = file_io.getvalue()

        transcribed_text = await voice_transcriber.transcribe_audio_bytes(audio_bytes)

        if not transcribed_text:
            await status_msg.edit_text("⚠️ Не удалось разобрать речь в аудиосообщении. Попробуйте записать ещё раз.")
            return

        # Удаляем временное статусное сообщение перед запуском генерации
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        except Exception:
            pass

        # Передаем транскрибированный текст в обработчик задач
        await _execute_prompt(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bot=bot,
            prompt_text=transcribed_text,
            reply_to_message_id=message.message_id,
            force_override=False
        )

    except Exception as e:
        logger.error(f"Ошибка обработки голосового сообщения: {e}", exc_info=True)
        try:
            await status_msg.edit_text(f"❌ <b>Ошибка распознавания речи:</b>\n<code>{str(e)}</code>", parse_mode="HTML")
        except Exception:
            await message.reply(f"❌ <b>Ошибка распознавания речи:</b>\n<code>{str(e)}</code>", parse_mode="HTML")


@router.message(F.photo)
async def handle_photo_message(message: types.Message, bot: Bot):
    """
    Обработчик фото и скриншотов:
    - Сохраняет фото в изолированную папку data/uploads/.
    - Передает абсолютный путь к фото мультимодальной модели Gemini.
    """
    photo = message.photo[-1]  # Берем максимальное разрешение
    ts = time.strftime("%Y%m%d_%H%M%S")
    uploads_dir = ensure_uploads_dir()
    file_path = uploads_dir / f"photo_{ts}.jpg"

    await bot.download(photo, destination=file_path)

    caption = message.caption or ""
    prompt_text = f"Пользователь прикрепил изображение: [photo_{ts}.jpg](file://{file_path.resolve()})\n\n{caption}".strip()

    await _execute_prompt(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        bot=bot,
        prompt_text=prompt_text,
        reply_to_message_id=message.message_id,
        force_override=False
    )


@router.message(F.document)
async def handle_document_message(message: types.Message, bot: Bot):
    """
    Обработчик прикрепленных файлов и документов:
    - Сохраняет файл в data/uploads/.
    - Передает путь модели.
    """
    doc = message.document
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in (doc.file_name or "file") if c.isalnum() or c in "._-")
    uploads_dir = ensure_uploads_dir()
    file_path = uploads_dir / f"{ts}_{safe_name}"

    await bot.download(doc, destination=file_path)

    caption = message.caption or ""
    prompt_text = f"Пользователь прикрепил документ: [{doc.file_name}](file://{file_path.resolve()})\n\n{caption}".strip()

    await _execute_prompt(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        bot=bot,
        prompt_text=prompt_text,
        reply_to_message_id=message.message_id,
        force_override=False
    )


@router.message(F.text.startswith("/get ") | F.text.startswith("/download "))
async def handle_get_file_command(message: types.Message, bot: Bot):
    """
    Команда /get <путь_к_файлу>:
    - Находит файл в текущем проекте на Mac.
    - Отправляет реальный файл документом в Telegram.
    """
    raw_path = message.text.split(" ", 1)[1].strip()
    session = session_manager.get_session(message.from_user.id)
    project_dir = session.current_project_dir

    target_path = Path(raw_path)
    if not target_path.is_absolute():
        target_path = project_dir / target_path

    if not target_path.exists():
        await message.reply(
            f"❌ <b>Файл не найден:</b> <code>{target_path}</code>\n\n"
            f"📁 Текущий проект: <code>{project_dir}</code>",
            parse_mode="HTML"
        )
        return

    if target_path.is_dir():
        await message.reply(
            f"⚠️ <code>{target_path.name}</code> — это папка, а не файл. Укажите конкретный файл или заархивируйте папку.",
            parse_mode="HTML"
        )
        return

    file_size_mb = target_path.stat().st_size / (1024 * 1024)
    if file_size_mb > 50:
        await message.reply(
            f"⚠️ Файл слишком большой для отправки через Telegram ({file_size_mb:.1f} MB > 50 MB лимит Telegram).",
            parse_mode="HTML"
        )
        return

    status_msg = await message.reply(f"📤 <i>Отправляю файл {target_path.name} ({file_size_mb:.2f} MB)...</i>", parse_mode="HTML")
    try:
        ext = target_path.suffix.lower()
        if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
            input_file = FSInputFile(path=str(target_path), filename=target_path.name)
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=input_file,
                caption=f"🖼 <b>Файл из проекта:</b> <code>{target_path.name}</code>",
                parse_mode="HTML"
            )
        else:
            input_file = prepare_attachment_file(target_path)
            await bot.send_document(
                chat_id=message.chat.id,
                document=input_file,
                caption=f"📄 <b>Файл из проекта:</b> <code>{target_path.name}</code>",
                parse_mode="HTML"
            )
        await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
    except Exception as e:
        logger.error(f"Ошибка отправки файла {target_path}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ <b>Ошибка отправки файла:</b>\n<code>{str(e)}</code>", parse_mode="HTML")
