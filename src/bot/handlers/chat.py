import io
import re
import time
import asyncio
import logging
from urllib.parse import unquote
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
from aiogram import Router, types, Bot, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from src.engine.session_manager import session_manager
from src.engine.antigravity_bridge import antigravity_bridge, EngineEvent
from src.engine.voice_transcriber import voice_transcriber
from src.engine.uploads_manager import ensure_uploads_dir
from src.bot.utils.formatter import format_thought_block, format_tool_call_block
from src.bot.utils.streamer import LiveStreamer
from src.bot.locales import t

logger = logging.getLogger(__name__)
router = Router(name="chat_router")

# Text extensions requiring UTF-8 BOM for iOS QuickLook preview
TEXT_FILE_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".csv", ".json", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".astro", ".html",
    ".css", ".sh", ".env", ".log", ".sql", ".xml"
}

_LAST_USER_PROMPT: Dict[int, str] = {}
_ACTIVE_USER_TASKS: Dict[int, asyncio.Task] = {}
_MEDIA_GROUPS: Dict[str, List[types.Message]] = {}
TASK_WATCHDOG_TIMEOUT_SECONDS = 300  # 5 minutes maximum turn runtime
MAX_QUEUE_SIZE = 10
_USER_QUEUES: Dict[int, asyncio.Queue] = {}


@dataclass
class QueuedPrompt:
    chat_id: int
    user_id: int
    bot: Bot
    prompt_text: str
    reply_to_message_id: Optional[int] = None
    force_override: bool = False
    notify_message_id: Optional[int] = None


def _get_user_queue(user_id: int) -> asyncio.Queue:
    if user_id not in _USER_QUEUES:
        _USER_QUEUES[user_id] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
    return _USER_QUEUES[user_id]


def prepare_attachment_file(file_path: Path):
    """
    Prepares a file for Telegram delivery.
    Adds UTF-8 BOM for plain text files to ensure iOS QuickLook displays Cyrillic & UTF-8 correctly.
    """
    ext = file_path.suffix.lower()
    if ext in TEXT_FILE_EXTENSIONS:
        try:
            raw_bytes = file_path.read_bytes()
            if not raw_bytes.startswith(b"\xef\xbb\xbf"):
                raw_bytes = b"\xef\xbb\xbf" + raw_bytes
            return BufferedInputFile(file=raw_bytes, filename=file_path.name)
        except Exception as e:
            logger.warning(f"Could not add BOM to {file_path}: {e}")
    return FSInputFile(path=str(file_path), filename=file_path.name)


def extract_attachment_paths(text: str) -> List[Path]:
    """
    Extracts local file and image paths referenced in the agent's output:
    - Markdown images: ![alt](/path/to/file)
    - Local file links: [text](file:///path/to/file)
    """
    found_paths = []

    img_matches = re.findall(r'!\[.*?\]\(([^)]+)\)', text)
    for match in img_matches:
        clean_str = unquote(match.replace("file://", "").strip())
        p = Path(clean_str)
        if p.is_file() and p.exists() and p not in found_paths:
            found_paths.append(p)

    file_matches = re.findall(r'\[.*?\]\(file://([^)]+)\)', text)
    for match in file_matches:
        clean_str = unquote(match.strip())
        p = Path(clean_str)
        if p.is_file() and p.exists() and p not in found_paths:
            found_paths.append(p)

    return found_paths


async def _execute_single_prompt(item: QueuedPrompt):
    """
    Executes a single prompt turn from the queue with LiveStreamer,
    session locking, watchdog timeout, and automatic attachment handling.
    """
    chat_id = item.chat_id
    user_id = item.user_id
    bot = item.bot
    prompt_text = item.prompt_text
    reply_to_message_id = item.reply_to_message_id
    force_override = item.force_override
    notify_message_id = item.notify_message_id

    # Clean up temporary "added to queue" notification message if it exists
    if notify_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=notify_message_id)
        except Exception:
            pass

    session = session_manager.get_session(user_id)
    active_chat = session.get_active_chat()
    lang = session.language

    _LAST_USER_PROMPT[user_id] = prompt_text
    effective_override = force_override or (not session.safety_approval)

    async with session.lock:
        streamer = LiveStreamer(bot=bot, chat_id=chat_id, reply_to_message_id=reply_to_message_id)
        await streamer.start()

        thought_blocks = []
        tool_blocks = []
        full_response_text = []
        was_cancelled = False

        if active_chat.messages_count == 0:
            clean_title = prompt_text[:30].replace("\n", " ").strip()
            active_chat.title = f"💬 {clean_title}..."

        active_chat.messages_count += 1
        active_chat.updated_at = time.time()

        try:
            async def _run_stream_loop():
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
                            thought_blocks.append(format_thought_block(str(event.content), lang=lang))
                    elif event.event_type == "tool_call":
                        tool_info = event.content or {}
                        tool_name = tool_info.get("name", "tool")
                        tool_args = tool_info.get("args", {})
                        tool_blocks.append(format_tool_call_block(tool_name, tool_args, lang=lang))
                    elif event.event_type == "token":
                        if event.content:
                            full_response_text.append(str(event.content))
                            await streamer.update_text(str(event.content))
                    elif event.event_type == "error":
                        err_lbl = "Execution error" if lang == "en" else "Ошибка выполнения"
                        thought_blocks.append(f"⚠️ <b>{err_lbl}:</b>\n<code>{event.content}</code>")

            await asyncio.wait_for(_run_stream_loop(), timeout=TASK_WATCHDOG_TIMEOUT_SECONDS)

        except asyncio.TimeoutError:
            logger.warning(f"Task for user {user_id} hit watchdog timeout ({TASK_WATCHDOG_TIMEOUT_SECONDS}s).")
            antigravity_bridge.cancel_active_task(user_id)
            timeout_lbl = "Task exceeded runtime limit (5 min watchdog timeout)" if lang == "en" else "Превышен лимит времени выполнения задачи (таймаут 5 мин)"
            thought_blocks.append(f"⏱ <b>{timeout_lbl}</b>")

        except asyncio.CancelledError:
            logger.info(f"Task for user {user_id} cancelled via /stop.")
            was_cancelled = True
            halt_lbl = "Task halted by user (/stop)" if lang == "en" else "Задача прервана пользователем (/stop)"
            thought_blocks.append(f"🛑 <b>{halt_lbl}</b>")
            raise

        except Exception as e:
            logger.error(f"Unhandled error in chat loop: {e}", exc_info=True)
            crit_lbl = "Critical agent error" if lang == "en" else "Критическая ошибка агента"
            thought_blocks.append(f"❌ <b>{crit_lbl}:</b>\n<code>{str(e)}</code>")

        finally:
            extra_blocks = thought_blocks + tool_blocks
            complete_output = "".join(full_response_text)

            kb = None
            if session.safety_approval and not force_override and not was_cancelled:
                if ("Permission denied" in complete_output or "deny rule" in complete_output or "заблокирован" in complete_output.lower()):
                    btn_text = t("btn_force_override", lang)
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=btn_text,
                                callback_data="force_execute"
                            )
                        ]
                    ])

            await streamer.finalize(extra_blocks=extra_blocks, reply_markup=kb)
            session_manager.save_to_disk()

            # Automatic delivery of images and files generated by the agent (if not cancelled)
            if not was_cancelled:
                attachments = extract_attachment_paths(complete_output)
                for file_path in attachments:
                    try:
                        file_size_mb = file_path.stat().st_size / (1024 * 1024)
                        if file_size_mb > 50:
                            logger.info(f"File {file_path.name} too large ({file_size_mb:.1f} MB), skipping.")
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
                        logger.info(f"Automatically delivered attachment: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Failed to auto-send attachment {file_path}: {e}")


async def _user_queue_worker(user_id: int):
    """
    Background worker loop for a single user that sequentially processes
    all items in their queue until the queue is completely drained.
    """
    queue = _get_user_queue(user_id)
    try:
        while not queue.empty():
            item: QueuedPrompt = await queue.get()
            try:
                await _execute_single_prompt(item)
            except asyncio.CancelledError:
                logger.info(f"Queue worker for user {user_id} cancelled.")
                break
            except Exception as e:
                logger.error(f"Error executing queued item for user {user_id}: {e}", exc_info=True)
            finally:
                queue.task_done()
    finally:
        _ACTIVE_USER_TASKS.pop(user_id, None)


async def _execute_prompt(
    chat_id: int,
    user_id: int,
    bot: Bot,
    prompt_text: str,
    reply_to_message_id: Optional[int] = None,
    force_override: bool = False
):
    """
    Entry point for all user prompts (text, audio, photos, documents).
    Routes prompts into the sequential queue or rejects based on session.queue_mode.
    """
    session = session_manager.get_session(user_id)
    lang = session.language
    queue = _get_user_queue(user_id)

    # Check if there is an active running task for this user
    active_task = _ACTIVE_USER_TASKS.get(user_id)
    is_busy = bool(active_task and not active_task.done())

    if is_busy:
        if session.queue_mode == "block":
            busy_msg = (
                "⏳ <b>Agent is currently executing a previous task.</b>\nPlease wait for completion or send /stop."
                if lang == "en" else
                "⏳ <b>Агент уже выполняет предыдущую задачу.</b>\nПожалуйста, дождитесь завершения или отправьте /stop."
            )
            await bot.send_message(
                chat_id=chat_id,
                text=busy_msg,
                reply_to_message_id=reply_to_message_id,
                parse_mode="HTML"
            )
            return

        # session.queue_mode == "queue"
        if queue.qsize() >= MAX_QUEUE_SIZE:
            limit_msg = t("queue_full", lang, limit=MAX_QUEUE_SIZE)
            await bot.send_message(
                chat_id=chat_id,
                text=limit_msg,
                reply_to_message_id=reply_to_message_id,
                parse_mode="HTML"
            )
            return

        pos = queue.qsize() + 1
        notify_text = t("msg_queued", lang, pos=pos)
        notify_msg = await bot.send_message(
            chat_id=chat_id,
            text=notify_text,
            reply_to_message_id=reply_to_message_id,
            parse_mode="HTML"
        )
        queued_item = QueuedPrompt(
            chat_id=chat_id,
            user_id=user_id,
            bot=bot,
            prompt_text=prompt_text,
            reply_to_message_id=reply_to_message_id,
            force_override=force_override,
            notify_message_id=notify_msg.message_id
        )
        await queue.put(queued_item)
        return

    # User is not busy: enqueue prompt and launch worker
    queued_item = QueuedPrompt(
        chat_id=chat_id,
        user_id=user_id,
        bot=bot,
        prompt_text=prompt_text,
        reply_to_message_id=reply_to_message_id,
        force_override=force_override,
        notify_message_id=None
    )
    await queue.put(queued_item)
    worker_task = asyncio.create_task(_user_queue_worker(user_id))
    _ACTIVE_USER_TASKS[user_id] = worker_task


async def _process_media_group(messages: List[types.Message], bot: Bot):
    """
    Combines an entire Telegram album (media group of photos/documents)
    into a single unified multimodal prompt for Gemini / Antigravity CLI.
    """
    if not messages:
        return
    first_msg = messages[0]
    user_id = first_msg.from_user.id
    chat_id = first_msg.chat.id
    ts = time.strftime("%Y%m%d_%H%M%S")
    uploads_dir = ensure_uploads_dir()

    # Find first non-empty caption in the album
    caption = ""
    for m in messages:
        if m.caption and m.caption.strip():
            caption = m.caption.strip()
            break

    file_links = []
    for idx, m in enumerate(messages, 1):
        if m.photo:
            photo = m.photo[-1]
            file_path = uploads_dir / f"photo_{ts}_{idx}.jpg"
            await bot.download(photo, destination=file_path)
            file_links.append(f"{idx}. [photo_{ts}_{idx}.jpg](file://{file_path.resolve()})")
        elif m.document:
            doc = m.document
            safe_name = "".join(c for c in (doc.file_name or "file") if c.isalnum() or c in "._-")
            file_path = uploads_dir / f"{ts}_{idx}_{safe_name}"
            await bot.download(doc, destination=file_path)
            file_links.append(f"{idx}. [{doc.file_name}](file://{file_path.resolve()})")

    file_list_str = "\n".join(file_links)
    session = session_manager.get_session(user_id)
    lang = session.language
    header = f"User attached an album with {len(file_links)} images/files:" if lang == "en" else f"Пользователь прикрепил альбом из {len(file_links)} изображений/файлов:"

    prompt_text = f"{header}\n{file_list_str}\n\n{caption}".strip()

    await _execute_prompt(
        chat_id=chat_id,
        user_id=user_id,
        bot=bot,
        prompt_text=prompt_text,
        reply_to_message_id=first_msg.message_id,
        force_override=False
    )


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
    session = session_manager.get_session(user_id)

    if not last_prompt:
        err_msg = "Could not find previous prompt." if session.language == "en" else "Не удалось найти предыдущий запрос."
        await callback.answer(f"⚠️ {err_msg}", show_alert=True)
        return

    notify = "Executing with one-time force override..." if session.language == "en" else "Запуск с разовым снятием защиты..."
    await callback.answer(f"⚡ {notify}")
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
    session = session_manager.get_session(user_id)
    last_prompt = _LAST_USER_PROMPT.get(user_id)

    if not last_prompt:
        no_prev = "No previous prompt found for force retry." if session.language == "en" else "Нет предыдущего запроса для повторного выполнения с пропуском защиты."
        await message.reply(f"⚠️ {no_prev}")
        return

    retry_notice = "<b>Rerunning with one-time force override...</b>" if session.language == "en" else "<b>Повторный запуск с разовым снятием защиты...</b>"
    await message.reply(f"⚡ {retry_notice}", parse_mode="HTML")
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
    /stop command:
    - Kills the running OS process group (CLI / tool subprocesses).
    - Cancels the underlying asyncio task, releasing the session lock immediately.
    - Drains and clears any pending items from the user queue.
    """
    user_id = message.from_user.id
    session = session_manager.get_session(user_id)
    lang = session.language

    # 1. Kill OS process and its children
    was_cancelled_proc = antigravity_bridge.cancel_active_task(user_id)

    # 2. Cancel active asyncio task
    active_task = _ACTIVE_USER_TASKS.get(user_id)
    was_cancelled_task = False
    if active_task and not active_task.done():
        active_task.cancel()
        was_cancelled_task = True

    # 3. Drain and clear pending queue
    queue = _get_user_queue(user_id)
    cleared_count = 0
    while not queue.empty():
        try:
            item: QueuedPrompt = queue.get_nowait()
            cleared_count += 1
            if item.notify_message_id:
                try:
                    await bot.delete_message(chat_id=item.chat_id, message_id=item.notify_message_id)
                except Exception:
                    pass
            queue.task_done()
        except Exception:
            break

    if was_cancelled_proc or was_cancelled_task or cleared_count > 0:
        if cleared_count > 0:
            await message.reply(t("task_stopped_with_queue", lang, count=cleared_count), parse_mode="HTML")
        else:
            await message.reply(t("task_stopped", lang), parse_mode="HTML")
    else:
        await message.reply(t("task_nothing_to_stop", lang), parse_mode="HTML")


@router.message(F.voice | F.audio)
async def handle_voice_message(message: types.Message, bot: Bot):
    session = session_manager.get_session(message.from_user.id)
    lang = session.language

    if not voice_transcriber.is_configured:
        notice = (
            "🎙️ <b>Voice Transcription Setup</b>\n\n"
            "⚠️ To enable instant voice transcription via <b>Groq Whisper Large v3 Turbo</b>, "
            "set your <code>GROQ_API_KEY</code> in the project's <code>.env</code> file.\n\n"
            "🔑 Obtain a free API key: <a href='https://console.groq.com/keys'>console.groq.com/keys</a>"
            if lang == "en" else
            "🎙️ <b>Распознавание голосовых сообщений</b>\n\n"
            "⚠️ Для мгновенной расшифровки через <b>Groq Whisper Large v3 Turbo</b>, "
            "укажите ваш <code>GROQ_API_KEY</code> в файле <code>.env</code> проекта.\n\n"
            "🔑 Получить бесплатный ключ: <a href='https://console.groq.com/keys'>console.groq.com/keys</a>"
        )
        await message.reply(notice, parse_mode="HTML", disable_web_page_preview=True)
        return

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    status_text = t("voice_processing", lang)
    status_msg = await message.reply(status_text, parse_mode="HTML")

    try:
        file_io = io.BytesIO()
        await bot.download(file=file_id, destination=file_io)
        audio_bytes = file_io.getvalue()

        transcribed_text = await voice_transcriber.transcribe_audio_bytes(audio_bytes)

        if not transcribed_text:
            err_text = "Could not parse audio speech. Please record again." if lang == "en" else "Не удалось разобрать речь в аудиосообщении. Попробуйте записать ещё раз."
            await status_msg.edit_text(f"⚠️ {err_text}")
            return

        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        except Exception:
            pass

        await _execute_prompt(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            bot=bot,
            prompt_text=transcribed_text,
            reply_to_message_id=message.message_id,
            force_override=False
        )

    except Exception as e:
        logger.error(f"Voice transcription error: {e}", exc_info=True)
        err_msg = t("voice_error", lang, error=str(e))
        try:
            await status_msg.edit_text(err_msg, parse_mode="HTML")
        except Exception:
            await message.reply(err_msg, parse_mode="HTML")


@router.message(F.photo)
async def handle_photo_message(message: types.Message, bot: Bot):
    if message.media_group_id:
        mg_id = message.media_group_id
        if mg_id not in _MEDIA_GROUPS:
            _MEDIA_GROUPS[mg_id] = [message]
            await asyncio.sleep(0.8)
            group_messages = _MEDIA_GROUPS.pop(mg_id, [])
            await _process_media_group(group_messages, bot)
        else:
            _MEDIA_GROUPS[mg_id].append(message)
        return

    # Single photo
    photo = message.photo[-1]
    ts = time.strftime("%Y%m%d_%H%M%S")
    uploads_dir = ensure_uploads_dir()
    file_path = uploads_dir / f"photo_{ts}.jpg"

    await bot.download(photo, destination=file_path)

    caption = message.caption or ""
    prompt_text = f"User attached image: [photo_{ts}.jpg](file://{file_path.resolve()})\n\n{caption}".strip()

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
    if message.media_group_id:
        mg_id = message.media_group_id
        if mg_id not in _MEDIA_GROUPS:
            _MEDIA_GROUPS[mg_id] = [message]
            await asyncio.sleep(0.8)
            group_messages = _MEDIA_GROUPS.pop(mg_id, [])
            await _process_media_group(group_messages, bot)
        else:
            _MEDIA_GROUPS[mg_id].append(message)
        return

    # Single document
    doc = message.document
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in (doc.file_name or "file") if c.isalnum() or c in "._-")
    uploads_dir = ensure_uploads_dir()
    file_path = uploads_dir / f"{ts}_{safe_name}"

    await bot.download(doc, destination=file_path)

    caption = message.caption or ""
    prompt_text = f"User attached document: [{doc.file_name}](file://{file_path.resolve()})\n\n{caption}".strip()

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
    raw_path = message.text.split(" ", 1)[1].strip()
    session = session_manager.get_session(message.from_user.id)
    lang = session.language
    project_dir = session.current_project_dir

    target_path = Path(raw_path)
    if not target_path.is_absolute():
        target_path = project_dir / target_path

    if not target_path.exists():
        not_found = t("get_file_not_found", lang, path=str(target_path))
        proj_label = "Active Project" if lang == "en" else "Текущий проект"
        await message.reply(
            f"{not_found}\n\n📁 {proj_label}: <code>{project_dir}</code>",
            parse_mode="HTML"
        )
        return

    if target_path.is_dir():
        is_dir_msg = "is a directory, not a file. Specify a specific file or compress it." if lang == "en" else "это папка, а не файл. Укажите конкретный файл или заархивируйте папку."
        await message.reply(
            f"⚠️ <code>{target_path.name}</code> — {is_dir_msg}",
            parse_mode="HTML"
        )
        return

    file_size_mb = target_path.stat().st_size / (1024 * 1024)
    if file_size_mb > 50:
        await message.reply(
            t("get_file_too_large", lang, size_mb=file_size_mb),
            parse_mode="HTML"
        )
        return

    sending_label = f"Sending {target_path.name} ({file_size_mb:.2f} MB)..." if lang == "en" else f"Отправляю файл {target_path.name} ({file_size_mb:.2f} MB)..."
    status_msg = await message.reply(f"📤 <i>{sending_label}</i>", parse_mode="HTML")
    try:
        ext = target_path.suffix.lower()
        file_caption = f"Project File: <code>{target_path.name}</code>" if lang == "en" else f"Файл из проекта: <code>{target_path.name}</code>"
        if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
            input_file = FSInputFile(path=str(target_path), filename=target_path.name)
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=input_file,
                caption=f"🖼 <b>{file_caption}</b>",
                parse_mode="HTML"
            )
        else:
            input_file = prepare_attachment_file(target_path)
            await bot.send_document(
                chat_id=message.chat.id,
                document=input_file,
                caption=f"📄 <b>{file_caption}</b>",
                parse_mode="HTML"
            )
        await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
    except Exception as e:
        logger.error(f"Error sending file {target_path}: {e}", exc_info=True)
        err_msg = f"Failed to send file: {e}" if lang == "en" else f"Ошибка отправки файла: {e}"
        await status_msg.edit_text(f"❌ <b>{err_msg}</b>", parse_mode="HTML")
