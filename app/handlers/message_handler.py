from telegram import Update
from telegram.ext import MessageHandler, ContextTypes, filters
from app.db.user_data import (
    create_or_update_user,
    get_current_session_history,
    append_message_to_current_session,
    mark_session_completed
)
from app.ai.agent import ask_ai
from config.logger import logger

# Global dictionaries
user_busy_flags = {}
user_pending_messages = {}

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name
    message_text = update.message.text.strip()

    # Check if user is busy
    if user_busy_flags.get(user_id, False):
        # Save message for later processing
        user_pending_messages.setdefault(user_id, []).append(message_text)
        await update.message.reply_text("لحظة بس أخلص الرد")
        return

    # Mark user as busy
    user_busy_flags[user_id] = True

    try:
        logger.info(f"📩 Message received from {first_name} ({user_id}): {message_text}")

        # Ensure user exists in DB
        create_or_update_user(user_id=user_id, first_name=first_name)

        # Get session history and append current message
        history = get_current_session_history(user_id)
        history.append({"role": "user", "content": message_text})

        # Send "typing" action
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Send to AI agent
        response = await ask_ai(user_id=user_id, message_history=history)

        # Check if there are pending messages waiting
        pending = user_pending_messages.get(user_id)
        if pending:
            logger.info(f"🔄 Found {len(pending)} pending messages for user {user_id}")

            # Merge all pending messages into one block
            merged_text = message_text + "\n" + "\n".join(pending)

            # Clear pending messages
            user_pending_messages[user_id] = []

            # Rebuild the conversation history
            history = get_current_session_history(user_id)
            history.append({"role": "user", "content": merged_text})

            # Send typing action again
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            # Send merged message to AI
            response = await ask_ai(user_id=user_id, message_history=history)

            reply = response.get("reply", "عذرًا، لم أتمكن من فهم طلبك.")
            session_end = response.get("session_end", False)
            summary = response.get("summary")

            # Save merged conversation
            append_message_to_current_session(user_id, {"role": "user", "content": merged_text})
            append_message_to_current_session(user_id, {"role": "assistant", "content": reply})

            # Send only the **final combined reply** to user
            await update.message.reply_text(reply)

            if session_end:
                mark_session_completed(user_id=user_id, summary=summary)
                logger.info(f"✅ Session completed for user {user_id}. Summary saved.")

            return  # We skip sending the first reply to avoid double replies

        # No pending messages → send first reply directly
        reply = response.get("reply", "عذرًا، لم أتمكن من فهم طلبك.")
        session_end = response.get("session_end", False)
        summary = response.get("summary")

        append_message_to_current_session(user_id, {"role": "user", "content": message_text})
        append_message_to_current_session(user_id, {"role": "assistant", "content": reply})

        await update.message.reply_text(reply)

        if session_end:
            mark_session_completed(user_id=user_id, summary=summary)
            logger.info(f"✅ Session completed for user {user_id}. Summary saved.")

    except Exception as e:
        logger.error(f"❌ Error processing message for user {user_id}: {e}")
        await update.message.reply_text("عذرًا، حدث خطأ أثناء المعالجة.")
    finally:
        # Always clear the busy flag
        user_busy_flags[user_id] = False


# Export the handler to be registered
message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message)
