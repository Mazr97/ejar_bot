import logging
import os

# Define logs directory path
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)  # Create the logs/ folder if it doesn't exist

# Define full log file path
log_file_path = os.path.join(log_dir, "bot.log")

# Create a custom logger
logger = logging.getLogger("bot_logger")
logger.setLevel(logging.DEBUG)  # Capture all log levels

# Create file handler and set level
file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Create console handler (optional)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger if not already added
if not logger.hasHandlers():
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
else:
    # Avoid adding multiple handlers if this file is imported more than once
    handlers = [type(h) for h in logger.handlers]
    if logging.FileHandler not in handlers:
        logger.addHandler(file_handler)
    if logging.StreamHandler not in handlers:
        logger.addHandler(console_handler)