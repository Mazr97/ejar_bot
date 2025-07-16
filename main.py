from app.bot import run_bot
from config.logger import logger

if __name__ == "__main__":
    logger.info("main.py started")
    run_bot()
