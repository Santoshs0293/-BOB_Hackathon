from fastapi import APIRouter, Depends
from ..database import db
from ..graph_store import G
from ..graph_detector import detect_suspicious_accounts
from ..crud import get_transactions as crud_get_transactions
from typing import Dict, Any
from bson import ObjectId
import asyncio
from ..scoring import full_score

router = APIRouter(prefix="/investigators", tags=["investigators"])

@router.get("/cases")
async def get_cases():
    txs = await crud_get_transactions(limit=50)
    flagged = [tx for tx in txs if tx.get("verdict") in ("fraud", "suspicious", "review", "block")]
    return {"cases": flagged}

@router.get("/alert/{account_number}")
async def alert_context(account_number: str):
    # run graph detector
    top = detect_suspicious_accounts(G)[:20]
    # fetch some recent transactions for account
    cursor = db.transactions.find({"account_number": account_number}).sort("timestamp", -1).limit(20)
    recent = []
    async for tx in cursor:
        tx["_id"] = str(tx["_id"])
        recent.append(tx)
    # score latest tx if exists
    explanation = None
    causal_summary = None
    if recent:
        latest = recent[0]
        tx_for_score = {
            "account_number": latest.get("account_number"),
            "amount": float(latest.get("amount", 0.0)),
            "currency": latest.get("currency", "INR"),
            "timestamp": latest.get("timestamp"),
            "metadata": latest.get("metadata", {})
        }
        score_res = await full_score(tx_for_score)
        explanation = score_res.get("explanation")
        causal_summary = score_res.get("causal_summary")
    return {
        "account": account_number,
        "recent_transactions": recent,
        "top_graph_suspicious": top,
        "explanation": explanation,
        "causal_summary": causal_summary
    }
