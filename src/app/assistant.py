from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

router = APIRouter(prefix="/assistant", tags=["assistant"])

# Use the same connection config as other modules
client = AsyncIOMotorClient(settings.MONGODB_URL)
db = client[settings.MONGO_DB_NAME]

@router.get("/explain/{tx_id}")
async def explain_transaction(tx_id: str):
    tx = await db.transactions.find_one({"_id": tx_id})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    expl = tx.get("explanation")
    if not expl:
        return {"note": "No explanation available"}

    # Natural language wrapper
    msg = f"""
    Transaction {tx_id} for account {tx['account_number']} of {tx['amount']} {tx['currency']}
    was scored {tx['score']:.2f} with verdict '{tx['verdict']}'.
    Explanation: {tx['explanation']}
    Analyst feedback: {tx.get('analyst_label', 'N/A')}
    """
    return {"narrative": msg.strip()}
