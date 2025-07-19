import asyncio
from config.logger import logger
import os
from datetime import datetime



# Global dictionaries for queues and workers
user_queues = {}
user_workers = {}

async def enqueue_message(user_id: int, chat_id: int, first_name: str, message_text: str):
    """
    Add a message to the user's queue.
    """
    queue = get_user_queue(user_id)
    await queue.put((chat_id, first_name, message_text))

    logger.info(f"📥 Queued message for user {user_id}: {message_text}")
    logger.debug(f"Queue size for user {user_id}: {queue.qsize()}")

    # Optional: Export queue to file for debugging
    #export_queue_to_file()

def get_user_queue(user_id: int) -> asyncio.Queue:
    """
    Get or create an asyncio.Queue for the user.
    """
    if user_id not in user_queues:
        user_queues[user_id] = asyncio.Queue()
        logger.debug(f"🆕 Created new queue for user {user_id}")
    return user_queues[user_id]

def is_worker_running(user_id: int) -> bool:
    """
    Check if a worker task is already running for this user.
    """
    running = user_id in user_workers
    logger.debug(f"👀 Worker running for user {user_id}: {running}")
    return running

def set_worker_task(user_id: int, task: asyncio.Task):
    """
    Store the asyncio task running for the user's queue.
    """
    user_workers[user_id] = task
    logger.debug(f"🔧 Set worker task for user {user_id}")

def queue_has_pending_messages(user_id: int) -> bool:
    """
    Check if a user's queue has pending messages.
    """
    queue = user_queues.get(user_id)
    has_pending = queue and not queue.empty()
    logger.debug(f"⏳ Pending messages for user {user_id}: {has_pending}")
    return has_pending

def clear_worker_task(user_id: int):
    """
    Remove the user's worker task from the tracking dict.
    """
    if user_id in user_workers:
        user_workers.pop(user_id, None)
        logger.debug(f"🧹 Cleared worker task for user {user_id}")

async def dequeue_message(user_id: int):
    """
    Get the next message from the user's queue.
    """
    queue = get_user_queue(user_id)
    message = await queue.get()
    logger.info(f"📤 Dequeued message for user {user_id}")
    return message

def mark_message_done(user_id: int):
    """
    Mark the current task as done for the user's queue.
    """
    queue = get_user_queue(user_id)
    queue.task_done()
    logger.debug(f"✅ Marked message as done for user {user_id}")

def delete_user_queue(user_id: int):
    """
    Optionally remove a user's queue entirely (cleanup).
    """
    if user_id in user_queues:
        user_queues.pop(user_id, None)
        logger.info(f"🗑️ Deleted queue for user {user_id}")


def export_queue_to_file():
    """
    Save the current contents of all user queues into a logs/queue_debug_<timestamp>.txt file.
    Creates logs/ folder if it doesn't exist.
    """
    # Generate dynamic file path with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_path = f"logs/queue_debug_{timestamp}.txt"

    # Ensure logs/ folder exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Write the table to file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"🕒 Queue Snapshot at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("+-----------+--------------+----------------------------+\n")
        f.write("| User ID   | First Name   | Message                    |\n")
        f.write("+-----------+--------------+----------------------------+\n")

        for user_id, queue in user_queues.items():
            for item in list(queue._queue):  # safe for reading
                chat_id, first_name, message_text = item
                f.write(f"| {str(user_id).ljust(9)} | {first_name.ljust(12)} | {message_text[:26].ljust(26)} |\n")

        f.write("+-----------+--------------+----------------------------+\n")

    print(f"✅ Queue snapshot exported to {file_path}")
