from datetime import datetime
import uuid
from app.db.mongo_client import users_collection, summaries_collection, sessions_collection


def get_user_by_id(user_id: int):
    """Return user document if exists."""
    return users_collection.find_one({"user_id": user_id})


def create_or_update_user(user_id: int, first_name: str = None, national_id: str = None, phone: str = None):
    """Create or update user record."""
    user_data = {
        "user_id": user_id,
        "updated_at": datetime.utcnow(),
    }

    if first_name:
        user_data["first_name"] = first_name
    if national_id:
        user_data["national_id"] = national_id
    if phone:
        user_data["phone"] = phone

    users_collection.update_one(
        {"user_id": user_id},
        {"$set": user_data, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True
    )


def get_partial_summary(user_id: int) -> str:
    """Retrieve the current session's partial summary."""
    session_id = get_current_session_id(user_id)
    if not session_id:
        return None

    session = sessions_collection.find_one({"_id": session_id})
    return session.get("partial_summary")

def update_partial_summary(user_id: int, summary: str):
    """Update the partial summary for the current session."""
    session_id = get_current_session_id(user_id)
    if not session_id:
        return

    sessions_collection.update_one(
        {"_id": session_id},
        {"$set": {
            "partial_summary": summary,
            "partial_summary_updated_at": datetime.utcnow()
        }}
    )





def get_user_profile(user_id: int):
    """Return user profile for Claude (dict format)."""
    user = get_user_by_id(user_id)
    if not user:
        return {}

    return {
        "first_name": user.get("first_name"),
        "national_id": user.get("national_id"),
        "phone": user.get("phone"),
    }


def create_new_session(user_id: int) -> str:
    """Create a new session for the user."""
    session_id = str(uuid.uuid4())
    session = {
        "_id": session_id,
        "user_id": user_id,
        "start_time": datetime.utcnow(),
        "end_time": None,
        "status": "active",
        "history": [],
    }
    sessions_collection.insert_one(session)

    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"current_session_id": session_id}}
    )

    return session_id


def get_current_session_id(user_id: int) -> str:
    """Get current active session ID."""
    user = get_user_by_id(user_id)
    return user.get("current_session_id") if user else None


def get_current_session_history(user_id: int) -> list:
    """Get the chat history from the current session."""
    session_id = get_current_session_id(user_id)
    if not session_id:
        return []

    session = sessions_collection.find_one({"_id": session_id})
    return session.get("history", []) if session else []


def append_message_to_current_session(user_id: int, message: dict):
    """Append a message to the user's current active session."""
    session_id = get_current_session_id(user_id)
    if not session_id:
        session_id = create_new_session(user_id)

    sessions_collection.update_one(
        {"_id": session_id},
        {"$push": {"history": message}}
    )


def mark_session_completed(user_id: int, summary: str = None):
    """Mark the current session as completed and unlink it from user."""
    session_id = get_current_session_id(user_id)
    if not session_id:
        return

    update_fields = {
        "status": "completed",
        "end_time": datetime.utcnow()
    }

    if summary:
        update_fields["final_summary"] = summary
        update_fields["final_summary_created_at"] = datetime.utcnow()

    sessions_collection.update_one(
        {"_id": session_id},
        {"$set": update_fields}
    )

    users_collection.update_one(
        {"user_id": user_id},
        {"$unset": {"current_session_id": ""}}
    )



def clear_current_session(user_id: int):
    """Remove history content from current session without ending it."""
    session_id = get_current_session_id(user_id)
    if not session_id:
        return

    sessions_collection.update_one(
        {"_id": session_id},
        {"$set": {"history": []}}
    )


def delete_user_data(user_id: int):
    """Delete all data related to a user (use with caution)."""
    user = get_user_by_id(user_id)
    session_id = user.get("current_session_id") if user else None

    # Remove session
    if session_id:
        sessions_collection.delete_one({"_id": session_id})

    # Remove all sessions
    sessions_collection.delete_many({"user_id": user_id})

    # Remove summary
    summaries_collection.delete_one({"user_id": user_id})

    # Remove user
    users_collection.delete_one({"user_id": user_id})
def get_final_summary(user_id: int) -> str:
    """Get the final summary if session is completed."""
    session_id = get_current_session_id(user_id)
    if not session_id:
        return None

    session = sessions_collection.find_one({"_id": session_id})
    return session.get("final_summary")
