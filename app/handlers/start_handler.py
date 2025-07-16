from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from app.db.user_data import create_or_update_user
from config.logger import logger


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name or "User"

    # Save user in DB
    create_or_update_user(user_id=user_id, first_name=first_name)

    logger.info(f"User {user_id} started the bot.")

    await update.message.reply_text(
      "أهلاً وسهلاً! أرسل أي رسالة للبدء."
    )

# Export the handler to be registered in bot.py
start_handler = CommandHandler("start", start)