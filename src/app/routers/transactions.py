from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from .. import schemas
from ..database import db
from .. import scoring
from ..explainability import synthesize_explanation
import json

router = APIRouter(prefix="/transactions", tags=["transactions"])

# ------------------------------------------
# Helper: convert Mongo doc to API-safe dict
# ------------------------------------------
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
        "causal_summary": tx_doc.get("causal_summary"),
        "top_graph_suspicious": tx_doc.get("top_graph_suspicious"),
        "graph_features": tx_doc.get("graph_features", {}),
        "analyst_label": tx_doc.get("analyst_label"),
        "analyst_notes": tx_doc.get("analyst_notes")
    }


# ------------------------------------------------------
# Create transaction, run full_score, persist explanation
# ------------------------------------------------------
@router.post("/ingest", response_model=schemas.TransactionOut)
async def ingest_transaction(tx_in: schemas.TransactionIn):
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
        "causal_summary": None,
        "top_graph_suspicious": None,
        "graph_features": {}
    }
    res = await db.transactions.insert_one(tx_doc)
    tx_id = res.inserted_id

    # Add graph edge immediately if device present
    try:
        device = tx_in.device
        if device and device.device_id:
            from ..graph_store import add_edge
            add_edge("account", tx_in.account_number, "device", device.device_id)
            await db.transactions.update_one(
                {"_id": tx_id},
                {"$set": {"metadata.device_id": device.device_id}}
            )
    except Exception:
        pass

    # Prepare tx for scoring
    tx_for_scoring = {
        "account_number": tx_in.account_number,
        "amount": float(tx_in.amount),
        "currency": tx_in.currency or "INR",
        "timestamp": datetime.utcnow(),
        "metadata": tx_in.metadata or {}
    }
    if tx_in.device and tx_in.device.device_id:
        tx_for_scoring["metadata"]["device_id"] = tx_in.device.device_id

    # Run scoring
    try:
        score_result = await scoring.full_score(tx_for_scoring)
    except Exception as e:
        await db.transactions.update_one(
            {"_id": tx_id}, {"$set": {"scoring_error": str(e)}}
        )
        raise HTTPException(status_code=500, detail=f"Scoring failed: {e}")

    # Build explanation text (human-friendly, with graph highlight)
    explanation = synthesize_explanation(
        tx_for_scoring["account_number"],
        tx_for_scoring,
        rules_score=score_result.get("rules_score", 0.0),
        ml_score=score_result.get("ml_score", 0.0),
        graph_score=score_result.get("graph_score", 0.0),
        causal_summary=score_result.get("causal_summary", {}),
        top_graph_suspicious=score_result.get("top_graph_suspicious", [])
    )

    # Persist scoring outputs
    update_payload = {
        "score": float(score_result.get("score", 0.0)),
        "verdict": score_result.get("verdict", "unknown"),
        "explanation": explanation,
        "causal_summary": score_result.get("causal_summary"),
        "top_graph_suspicious": score_result.get("top_graph_suspicious"),
        "graph_features": score_result.get("graph_features", {})
    }
    await db.transactions.update_one({"_id": tx_id}, {"$set": update_payload})

    saved = await db.transactions.find_one({"_id": tx_id})
    return _tx_to_out(saved)


# ---------------------------------
# Recent transactions (for UI list)
# ---------------------------------
@router.get("/recent")
async def recent_transactions(limit: int = 20):
    cursor = db.transactions.find().sort("timestamp", -1).limit(int(limit))
    results = []
    async for tx in cursor:
        results.append(_tx_to_out(tx))
    return results


# ----------------------------------------
# Get explanation for a single transaction
# ----------------------------------------
@router.get("/explain/{tx_id}")
async def get_explanation(tx_id: str):
    try:
        oid = ObjectId(tx_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid tx_id")

    tx = await db.transactions.find_one({"_id": oid})
    if not tx:
        raise HTTPException(status_code=404, detail="transaction not found")
    return _tx_to_out(tx)


# -----------------------
# Analyst feedback API
# -----------------------
@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def feedback(
    tx_id: str,
    analyst: Optional[str] = None,
    label: Optional[str] = None,
    notes: Optional[str] = None
):
    try:
        oid = ObjectId(tx_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid tx_id")

    tx = await db.transactions.find_one({"_id": oid})
    if not tx:
        raise HTTPException(status_code=404, detail="transaction not found")

    fb = {
        "tx_id": str(oid),
        "account_number": tx.get("account_number"),
        "analyst": analyst,
        "label": label,
        "notes": notes,
        "timestamp": datetime.utcnow()
    }
    # store in singular collection only
    await db.feedback.insert_one(fb)

    # push retrain flag into redis
    try:
        import redis
        from ..config import settings
        r = redis.from_url(settings.REDIS_URL)
        r.lpush(
            "ueba:feedback_queue",
            json.dumps({"tx_id": str(oid), "label": label, "analyst": analyst, "notes": notes})
        )
    except Exception:
        pass

    # update transaction with analyst info
    if label:
        await db.transactions.update_one(
            {"_id": oid},
            {"$set": {"analyst_label": label, "analyst_notes": notes}}
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"status": "ok", "tx_id": str(oid)}
    )
