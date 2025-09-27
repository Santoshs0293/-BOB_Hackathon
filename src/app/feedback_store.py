from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings
from datetime import datetime

client = AsyncIOMotorClient(settings.DATABASE_URL.replace("mongodb+srv", "mongodb"))
db = client.get_database("ueba_db")

async def save_feedback(tx_id: str, analyst: str, label: str, notes: str = None):
    doc = {
        "tx_id": tx_id,
        "analyst": analyst,
        "label": label,
        "notes": notes,
        "created_at": datetime.utcnow()
    }
    await db.feedbacks.insert_one(doc)
    return doc

async def get_all_feedback(limit: int = 50):
    cursor = db.feedbacks.find().sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)
