import os
from telegram.ext import Application
from dotenv import load_dotenv
from config.logger import logger  # Import the logger
from app.handlers.start_handler import start_handler
from app.handlers.message_handler import message_handler


# Load environment variables
load_dotenv()

# Get the bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logger.critical("BOT_TOKEN is not set in the .env file")
    raise ValueError("BOT_TOKEN is not set in the .env file")

# Initialize the Telegram bot application
app = Application.builder().token(BOT_TOKEN).build()

# Placeholder for handler registration
def register_handlers(application: Application):
    logger.debug("Registering handlers...")
    application.add_handler(start_handler)
    application.add_handler(message_handler)

# Entry point to run the bot
def run_bot():
    logger.info("Starting the bot...")
    register_handlers(app)
    app.run_polling()