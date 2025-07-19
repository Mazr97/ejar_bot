import asyncio
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import MessageHandler, ContextTypes, filters

from config import queue as user_queue
from config.logger import logger

from app.db.user_data import (
    create_or_update_user,
    get_current_session_history,
    append_message_to_current_session,
    mark_session_completed
)
from app.ai.agent import ask_ai_sync  # updated sync wrapper with streaming

# ── Debounce setup ─────────────────────────────────────────────────────────────
DEBOUNCE_SECONDS = 1.0
_debounce_buffers: dict[int, list[str]] = {}
_debounce_tasks:   dict[int, asyncio.Task] = {}

async def _flush_debounce(
    user_id: int,
    chat_id: int,
    first_name: str,
    context: ContextTypes.DEFAULT_TYPE
):
    """Send the buffered messages as one combined request."""
    msgs = _debounce_buffers.pop(user_id, [])
    if not msgs:
        return

    combined_text = "\n".join(msgs)
    logger.info(f"🔄 Debounced for user {user_id}: {len(msgs)} messages combined")

    # Enqueue combined text
    await user_queue.enqueue_message(user_id, chat_id, first_name, combined_text)
    if not user_queue.is_worker_running(user_id):
        task = asyncio.create_task(process_user_queue(user_id, context))
        user_queue.set_worker_task(user_id, task)

async def _schedule_flush(
    user_id: int,
    chat_id: int,
    first_name: str,
    context: ContextTypes.DEFAULT_TYPE
):
    """Wait for DEBOUNCE_SECONDS, then flush; cancel if a new message arrives."""
    try:
        await asyncio.sleep(DEBOUNCE_SECONDS)
        await _flush_debounce(user_id, chat_id, first_name, context)
    except asyncio.CancelledError:
        # New message arrived—this flush is cancelled
        pass

# ── Handlers ───────────────────────────────────────────────────────────────────

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    first_name = user.first_name
    text    = update.message.text.strip()

    # 1️⃣ Add incoming text to debounce buffer
    buf = _debounce_buffers.setdefault(user_id, [])
    buf.append(text)

    # 2️⃣ Cancel any existing scheduled flush
    prev_task = _debounce_tasks.get(user_id)
    if prev_task and not prev_task.done():
        prev_task.cancel()

    # 3️⃣ Schedule a new flush after DEBOUNCE_SECONDS
    _debounce_tasks[user_id] = asyncio.create_task(
        _schedule_flush(user_id, chat_id, first_name, context)
    )

async def process_user_queue(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    loop = asyncio.get_running_loop()
    try:
        # Drain the queue one combined message at a time
        while user_queue.queue_has_pending_messages(user_id):
            chat_id, first_name, text = await user_queue.dequeue_message(user_id)

            # — start continuous typing indicator —
            stop_evt = asyncio.Event()
            async def continuous_typing():
                while not stop_evt.is_set():
                    await context.bot.send_chat_action(
                        chat_id=chat_id,
                        action=ChatAction.TYPING
                    )
                    await asyncio.sleep(1.0)
            typing_task = asyncio.create_task(continuous_typing())

            # — record user & build history —
            create_or_update_user(user_id=user_id, first_name=first_name)
            history = get_current_session_history(user_id)
            history.append({"role": "user", "content": text})

            # — call the blocking AI in an executor —
            response = await loop.run_in_executor(
                None,
                lambda: ask_ai_sync(
                    user_id=user_id,
                    message_history=history
                )
            )

            # — extract reply & flags —
            reply       = response.get("reply", "عذراً، لم أفهم طلبك.")
            session_end = response.get("session_end", False)
            summary     = response.get("summary")

            # — log both sides in Mongo —
            append_message_to_current_session(
                user_id, {"role": "user", "content": text}
            )
            append_message_to_current_session(
                user_id, {"role": "assistant", "content": reply}
            )

            # — split and send long reply —
            CHUNK_SIZE = 4000
            for i in range(0, len(reply), CHUNK_SIZE):
                await context.bot.send_message(chat_id=chat_id, text=reply[i:i+CHUNK_SIZE])

            # — stop the typing loop —
            stop_evt.set()
            await typing_task

            # — finalize session if needed —
            if session_end:
                mark_session_completed(user_id=user_id, summary=summary)
                logger.info(f"Session completed for user {user_id}")

            user_queue.mark_message_done(user_id)

    except Exception as e:
        logger.error(f"Error in user {user_id} queue: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="عذراً، حدث خطأ أثناء المعالجة."
            )
        except:
            logger.error("Failed to send fallback error message.")
    finally:
        user_queue.clear_worker_task(user_id)

# Export the handler to your dispatcher
message_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    handle_user_message
)
