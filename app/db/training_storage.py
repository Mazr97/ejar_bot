from datetime import datetime
from app.db.mongo_client import  training_data

def store_for_training(prompt: str, completion: str):
    total = training_data.count_documents({})
    batch_number = (total // 200) + 1

    doc = {
        "prompt": prompt.strip(),
        "completion": completion.strip(),
        "timestamp": datetime.utcnow(),
        "batch": batch_number,
        "status": "raw",
        "source": "ai"
    }

    training_data.insert_one(doc)
