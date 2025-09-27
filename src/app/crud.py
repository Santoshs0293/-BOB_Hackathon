from .database import db
from datetime import datetime
from bson import ObjectId

async def create_transaction(account_number: str, amount: float, currency: str, merchant: str, metadata: dict):
    tx = {
        "account_number": account_number,
        "amount": amount,
        "currency": currency,
        "merchant": merchant,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow(),
        "score": 0.0,
        "verdict": "unknown"
    }
    result = await db.transactions.insert_one(tx)
    tx["_id"] = str(result.inserted_id)
    return tx

async def update_transaction_score(tx_id: str, score: float, verdict: str):
    await db.transactions.update_one(
        {"_id": ObjectId(tx_id)},
        {"$set": {"score": score, "verdict": verdict}}
    )

async def get_transactions(limit: int = 20):
    cursor = db.transactions.find().sort("timestamp", -1).limit(limit)
    results = []
    async for tx in cursor:
        tx["_id"] = str(tx["_id"])
        results.append(tx)
    return results
