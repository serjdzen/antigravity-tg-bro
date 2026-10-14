import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from aiogram import types, Bot
from src.bot.handlers.chat import (
    _execute_prompt,
    _execute_single_prompt,
    _user_queue_worker,
    _get_user_queue,
    handle_stop_command,
    QueuedPrompt,
    _USER_QUEUES,
    _ACTIVE_USER_TASKS,
    _LAST_USER_PROMPT,
    MAX_QUEUE_SIZE
)
from src.engine.session_manager import session_manager, UserSession
from src.engine.antigravity_bridge import EngineEvent
from src.bot.locales import t


class TestMessageQueue(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.user_id = 999111
        self.chat_id = 123456
        self.session = session_manager.get_session(self.user_id)
        self.session.queue_mode = "queue"
        self.session.language = "en"
        self.session.safety_approval = True

        # Clean up any leftover global state for this user
        _USER_QUEUES.pop(self.user_id, None)
        _ACTIVE_USER_TASKS.pop(self.user_id, None)
        _LAST_USER_PROMPT.pop(self.user_id, None)

        # Mock Bot
        self.bot = MagicMock(spec=Bot)
        self.bot.send_message = AsyncMock(return_value=MagicMock(message_id=777))
        self.bot.delete_message = AsyncMock()

    def tearDown(self):
        # Cancel any active tasks
        task = _ACTIVE_USER_TASKS.pop(self.user_id, None)
        if task and not task.done():
            task.cancel()
        _USER_QUEUES.pop(self.user_id, None)
        _LAST_USER_PROMPT.pop(self.user_id, None)

    async def test_1_sequential_fifo_execution_order(self):
        """
        Tests that prompts in queue execute strictly in First-In-First-Out (FIFO) sequence.
        """
        execution_order = []

        async def fake_stream_chat(**kwargs):
            p = kwargs.get("prompt")
            execution_order.append(f"start:{p}")
            await asyncio.sleep(0.05)
            yield EngineEvent(event_type="token", content=f"Response to {p}")
            execution_order.append(f"end:{p}")

        with patch("src.bot.handlers.chat.antigravity_bridge.stream_chat", side_effect=fake_stream_chat):
            # Prompt 1 starts worker
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Prompt 1"
            )

            # Prompt 2 and Prompt 3 are queued
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Prompt 2"
            )
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Prompt 3"
            )

            # Wait for worker task to complete all items
            worker_task = _ACTIVE_USER_TASKS.get(self.user_id)
            self.assertIsNotNone(worker_task)
            await worker_task

            # Verify execution order is strictly FIFO
            self.assertEqual(execution_order, [
                "start:Prompt 1", "end:Prompt 1",
                "start:Prompt 2", "end:Prompt 2",
                "start:Prompt 3", "end:Prompt 3"
            ])
            self.assertEqual(_LAST_USER_PROMPT.get(self.user_id), "Prompt 3")

    async def test_2_block_mode_rejection(self):
        """
        Tests that when queue_mode is 'block', subsequent messages while busy
        are immediately rejected and NOT added to queue.
        """
        self.session.queue_mode = "block"

        async def fake_slow_stream(**kwargs):
            await asyncio.sleep(0.2)
            yield EngineEvent(event_type="token", content="Done")

        with patch("src.bot.handlers.chat.antigravity_bridge.stream_chat", side_effect=fake_slow_stream):
            # Start prompt 1
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Prompt 1"
            )

            # Attempt prompt 2 while busy
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Prompt 2"
            )

            queue = _get_user_queue(self.user_id)
            # Queue must NOT have prompt 2
            self.assertEqual(queue.qsize(), 0)

            # User must receive busy rejection notice
            self.bot.send_message.assert_called()
            sent_args, sent_kwargs = self.bot.send_message.call_args
            self.assertIn("Agent is currently executing a previous task", sent_kwargs.get("text", ""))

            # Clean up worker
            worker_task = _ACTIVE_USER_TASKS.get(self.user_id)
            if worker_task:
                await worker_task

    async def test_3_queue_overflow_protection(self):
        """
        Tests that exceeding MAX_QUEUE_SIZE (10) sends queue_full warning
        and does not exceed capacity.
        """
        async def fake_infinite_stream(**kwargs):
            await asyncio.sleep(10)
            yield EngineEvent(event_type="token", content="Never")

        with patch("src.bot.handlers.chat.antigravity_bridge.stream_chat", side_effect=fake_infinite_stream):
            # Start active prompt
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Active Prompt"
            )

            # Fill up the queue to MAX_QUEUE_SIZE (10 items)
            for i in range(1, MAX_QUEUE_SIZE + 1):
                await _execute_prompt(
                    chat_id=self.chat_id,
                    user_id=self.user_id,
                    bot=self.bot,
                    prompt_text=f"Queued Prompt {i}"
                )

            queue = _get_user_queue(self.user_id)
            self.assertEqual(queue.qsize(), MAX_QUEUE_SIZE)

            # Attempt to add the 11th prompt (overflow)
            self.bot.send_message.reset_mock()
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Overflow Prompt 11"
            )

            # Queue must still be capped at MAX_QUEUE_SIZE
            self.assertEqual(queue.qsize(), MAX_QUEUE_SIZE)

            # Rejection message must warn about full queue
            sent_args, sent_kwargs = self.bot.send_message.call_args
            self.assertIn("Queue is full", sent_kwargs.get("text", ""))

            # Cancel task to clean up
            worker = _ACTIVE_USER_TASKS.get(self.user_id)
            if worker:
                worker.cancel()

    async def test_4_stop_command_cancels_task_and_clears_queue(self):
        """
        Tests that /stop kills the active process group, cancels worker,
        drains the entire queue, deletes temporary notification messages,
        and reports the count of cleared tasks.
        """
        async def fake_long_stream(**kwargs):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise
            yield EngineEvent(event_type="token", content="Done")

        with patch("src.bot.handlers.chat.antigravity_bridge.stream_chat", side_effect=fake_long_stream), \
             patch("src.bot.handlers.chat.antigravity_bridge.cancel_active_task", return_value=True) as mock_cancel:

            # Start active prompt
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Active Task"
            )

            # Queue 2 tasks
            self.bot.send_message.return_value = MagicMock(message_id=881)
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Queued 1"
            )

            self.bot.send_message.return_value = MagicMock(message_id=882)
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Queued 2"
            )

            queue = _get_user_queue(self.user_id)
            self.assertEqual(queue.qsize(), 2)

            # User sends /stop
            mock_stop_msg = MagicMock(spec=types.Message)
            mock_stop_msg.from_user = MagicMock(id=self.user_id)
            mock_stop_msg.reply = AsyncMock()

            await handle_stop_command(mock_stop_msg, self.bot)

            # 1. Bridge cancel called
            mock_cancel.assert_called_once_with(self.user_id)

            # 2. Queue drained to 0
            self.assertEqual(queue.qsize(), 0)

            # 3. Notification messages cleaned up
            self.bot.delete_message.assert_any_call(chat_id=self.chat_id, message_id=881)
            self.bot.delete_message.assert_any_call(chat_id=self.chat_id, message_id=882)

            # 4. Message reports that 2 tasks were cleared
            mock_stop_msg.reply.assert_called_once()
            reply_text = mock_stop_msg.reply.call_args[0][0]
            self.assertIn("Cleared <b>2</b> pending request(s)", reply_text)

    async def test_5_temporary_notification_cleaned_on_turn_start(self):
        """
        Tests that when a queued prompt begins execution, its temporary
        'added to queue' message is deleted from Telegram.
        """
        async def fake_stream(**kwargs):
            yield EngineEvent(event_type="token", content="Answer")

        with patch("src.bot.handlers.chat.antigravity_bridge.stream_chat", side_effect=fake_stream):
            item = QueuedPrompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Queued Item",
                notify_message_id=999
            )

            await _execute_single_prompt(item)

            # bot.delete_message must have been called for 999
            self.bot.delete_message.assert_any_call(chat_id=self.chat_id, message_id=999)

    async def test_6_error_isolation_in_queue_worker(self):
        """
        Tests that if one task in queue encounters an unhandled exception,
        the worker does not crash and proceeds to execute the next task in queue.
        """
        call_log = []

        async def buggy_stream_chat(**kwargs):
            p = kwargs.get("prompt")
            call_log.append(p)
            await asyncio.sleep(0.05)
            if p == "Buggy Prompt":
                raise RuntimeError("Catastrophic test failure")
            yield EngineEvent(event_type="token", content="Success")

        with patch("src.bot.handlers.chat.antigravity_bridge.stream_chat", side_effect=buggy_stream_chat):
            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Buggy Prompt"
            )
            worker = _ACTIVE_USER_TASKS.get(self.user_id)
            self.assertIsNotNone(worker)

            await _execute_prompt(
                chat_id=self.chat_id,
                user_id=self.user_id,
                bot=self.bot,
                prompt_text="Good Prompt"
            )

            await worker

            # Both prompts must have been attempted
            self.assertEqual(call_log, ["Buggy Prompt", "Good Prompt"])
            # Worker must have finished and cleaned itself up
            self.assertNotIn(self.user_id, _ACTIVE_USER_TASKS)

    async def test_7_multi_user_queue_isolation(self):
        """
        Tests that User A having an active task does not block User B
        from executing their prompt immediately.
        """
        user_a = 111001
        user_b = 222002

        user_b_executed = False

        async def stream_a(**kwargs):
            await asyncio.sleep(0.3)
            yield EngineEvent(event_type="token", content="User A result")

        async def stream_b(**kwargs):
            nonlocal user_b_executed
            await asyncio.sleep(0.1)
            user_b_executed = True
            yield EngineEvent(event_type="token", content="User B result")

        def side_effect(**kwargs):
            uid = kwargs.get("user_id")
            if uid == user_a:
                return stream_a(**kwargs)
            return stream_b(**kwargs)

        with patch("src.bot.handlers.chat.antigravity_bridge.stream_chat", side_effect=side_effect):
            # User A starts task
            await _execute_prompt(chat_id=1, user_id=user_a, bot=self.bot, prompt_text="A1")
            self.assertIn(user_a, _ACTIVE_USER_TASKS)

            # User B starts task
            await _execute_prompt(chat_id=2, user_id=user_b, bot=self.bot, prompt_text="B1")
            self.assertIn(user_b, _ACTIVE_USER_TASKS)

            # Wait for B to finish
            await _ACTIVE_USER_TASKS[user_b]
            self.assertTrue(user_b_executed)

            # Wait for A to finish
            await _ACTIVE_USER_TASKS[user_a]

            _ACTIVE_USER_TASKS.pop(user_a, None)
            _ACTIVE_USER_TASKS.pop(user_b, None)
            _USER_QUEUES.pop(user_a, None)
            _USER_QUEUES.pop(user_b, None)

    async def test_8_stop_when_nothing_is_running(self):
        """
        Tests that /stop when nothing is running reports 'nothing to stop'.
        """
        mock_stop_msg = MagicMock(spec=types.Message)
        mock_stop_msg.from_user = MagicMock(id=self.user_id)
        mock_stop_msg.reply = AsyncMock()

        with patch("src.bot.handlers.chat.antigravity_bridge.cancel_active_task", return_value=False):
            await handle_stop_command(mock_stop_msg, self.bot)
            mock_stop_msg.reply.assert_called_once()
            reply_text = mock_stop_msg.reply.call_args[0][0]
            self.assertIn("No active task", reply_text)


if __name__ == "__main__":
    unittest.main()
