from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI not found in .env")

client = MongoClient(MONGO_URI)

db = client["ejar_bot"]  # or "sukoon_db" if that's your DB

# Collections
users_collection = db["users"]
summaries_collection = db["summaries"]
sessions_collection = db["sessions"]  

training_data = db["training_data"]