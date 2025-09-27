from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi import status
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from .. import schemas
from ..database import db
from .. import scoring
import asyncio
import json

router = APIRouter(prefix="/transactions", tags=["transactions"])

# Helper: convert Mongo doc to API-safe dict
def _tx_to_out(tx_doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(tx_doc.get("_id")),
        "account_number": tx_doc.get("account_number"),
        "amount": float(tx_doc.get("amount", 0.0)),
        "currency": tx_doc.get("currency", "INR"),
        "merchant": tx_doc.get("merchant"),
        "metadata": tx_doc.get("metadata", {}),
        "timestamp": tx_doc.get("timestamp"),
        "score": float(tx_doc.get("score", 0.0)),
        "verdict": tx_doc.get("verdict", "unknown"),
        "explanation": tx_doc.get("explanation"),
        "causal_summary": tx_doc.get("causal_summary")
    }

# Create transaction, run full_score synchronously (await) and persist explanation & causal summary
@router.post("/ingest", response_model=schemas.TransactionOut)
async def ingest_transaction(tx_in: schemas.TransactionIn):
    """
    Ingest a transaction, run full scoring pipeline (rules + ml + graph + causal),
    store result and return final scoring + explanation & causal summary.
    Note: running full_score here means the API waits until scoring finishes (useful for demo).
    For high-throughput systems you can keep a fast-path and compute full_score in background.
    """
    # 1) persist optimistic record (score 0, verdict unknown) with timestamp
    tx_doc = {
        "account_number": tx_in.account_number,
        "amount": float(tx_in.amount),
        "currency": tx_in.currency or "INR",
        "merchant": tx_in.merchant,
        "metadata": tx_in.metadata or {},
        "timestamp": datetime.utcnow(),
        "score": 0.0,
        "verdict": "unknown",
        "explanation": None,
        "causal_summary": None
    }
    res = await db.transactions.insert_one(tx_doc)
    tx_id = res.inserted_id

    # 2) add graph edge immediately if device is present (helps graph scoring)
    try:
        device = tx_in.device
        if device:
            # use simple add_edge (synchronous; graph is in-memory)
            from ..graph_store import add_edge
            add_edge("account", tx_in.account_number, "device", device.device_id)
            # also record device id into metadata for persistence
            await db.transactions.update_one({"_id": tx_id}, {"$set": {"metadata.device_id": device.device_id}})
    except Exception:
        # non-fatal - continue scoring even if graph update fails
        pass

    # 3) Prepare tx for scoring
    tx_for_scoring = {
        "account_number": tx_in.account_number,
        "amount": float(tx_in.amount),
        "currency": tx_in.currency or "INR",
        "timestamp": datetime.utcnow(),
        "metadata": tx_in.metadata or {}
    }
    # if device present, place in metadata for scoring
    if tx_in.device and tx_in.device.device_id:
        tx_for_scoring["metadata"]["device_id"] = tx_in.device.device_id

    # 4) Run full_score (async). This returns score, verdict, explanation, causal_summary, top_graph_suspicious
    try:
        score_result = await scoring.full_score(tx_for_scoring)
    except Exception as e:
        # If scoring fails, return allowed optimistic response but log the error in DB
        await db.transactions.update_one({"_id": tx_id}, {"$set": {"scoring_error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Scoring failed: {e}")

    # 5) Persist the results into Mongo
    update_payload = {
        "score": float(score_result.get("score", 0.0)),
        "verdict": score_result.get("verdict", "unknown"),
        "explanation": score_result.get("explanation"),
        "causal_summary": score_result.get("causal_summary"),
        "top_graph_suspicious": score_result.get("top_graph_suspicious")
    }
    await db.transactions.update_one({"_id": tx_id}, {"$set": update_payload})

    # 6) Return the stored object (fresh)
    saved = await db.transactions.find_one({"_id": tx_id})
    return _tx_to_out(saved)


@router.get("/recent")
async def recent_transactions(limit: int = 20):
    """
    Return recent transactions (most recent first). Useful for UI list.
    """
    cursor = db.transactions.find().sort("timestamp", -1).limit(int(limit))
    results = []
    async for tx in cursor:
        results.append(_tx_to_out(tx))
    return results


@router.get("/explain/{tx_id}")
async def get_explanation(tx_id: str):
    """
    Return the explanation + causal summary for a transaction (if present).
    """
    try:
        oid = ObjectId(tx_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid tx_id")

    tx = await db.transactions.find_one({"_id": oid})
    if not tx:
        raise HTTPException(status_code=404, detail="transaction not found")
    return {
        "id": str(tx["_id"]),
        "account_number": tx.get("account_number"),
        "score": float(tx.get("score", 0.0)),
        "verdict": tx.get("verdict"),
        "explanation": tx.get("explanation"),
        "causal_summary": tx.get("causal_summary"),
        "top_graph_suspicious": tx.get("top_graph_suspicious")
    }


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def feedback(tx_id: str, analyst: Optional[str] = None, label: Optional[str] = None, notes: Optional[str] = None):
    """
    Analyst feedback endpoint:
    - tx_id: id of the transaction (string)
    - analyst: optional analyst id/email
    - label: analyst label (e.g., 'fraud', 'legit', 'suspicious')
    - notes: free text notes

    This stores the feedback and also writes a simple retrain flag in Redis so a background job can pick it up.
    """
    try:
        oid = ObjectId(tx_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid tx_id")

    tx = await db.transactions.find_one({"_id": oid})
    if not tx:
        raise HTTPException(status_code=404, detail="transaction not found")

    fb = {
        "tx_id": oid,
        "account_number": tx.get("account_number"),
        "analyst": analyst,
        "label": label,
        "notes": notes,
        "timestamp": datetime.utcnow()
    }
    await db.feedback.insert_one(fb)

    # write a retrain flag into Redis (simple queue key). Use a list push so a worker can pop.
    try:
        import redis
        from ..config import settings
        r = redis.from_url(settings.REDIS_URL)
        # store a small JSON with tx id and label
        r.lpush("ueba:feedback_queue", json.dumps({"tx_id": str(oid), "label": label, "analyst": analyst}))
    except Exception:
        # not fatal; just continue
        pass

    # Optionally update the original transaction verdict to analyst label for traceability
    if label:
        await db.transactions.update_one({"_id": oid}, {"$set": {"analyst_label": label, "analyst_notes": notes}})

    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"status": "ok", "tx_id": str(oid)})

