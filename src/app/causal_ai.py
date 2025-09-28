"""
Simple causal inference pipeline using DoWhy.
We will:
 - Build a binary label `is_fraud` from verdict (fraud/suspicious -> 1, else 0)
 - Build a small dataframe of features from recent transactions:
    - amount (numeric)
    - device_changed (binary: whether transaction device is new for that account)
    - geo_abroad (binary)
 - Use DoWhy to estimate effect of device_changed on is_fraud using linear regression (backdoor adjustment).
Note: This module is intentionally simple and CPU-friendly.
"""
import pandas as pd
from dowhy import CausalModel
from typing import List, Dict, Any
from .database import db
from bson import ObjectId
import asyncio

async def build_recent_tx_dataframe(limit: int = 200):
    """
    Pull recent transactions and assemble a DataFrame.
    Each row: account_number, amount, device_changed, geo_abroad, is_fraud
    """
    cursor = db.transactions.find().sort("timestamp", -1).limit(limit)
    rows = []
    # build a simple mapping of account -> set of seen devices
    account_devices = {}
    async for tx in cursor:
        acct = tx.get("account_number")
        metadata = tx.get("metadata") or {}
        device_id = metadata.get("device_id") or (tx.get("metadata") or {}).get("device_id")
        geo = metadata.get("geo") or metadata.get("country") or None
        is_fraud = 1 if tx.get("verdict") in ("fraud", "suspicious") else 0
        prev_devices = account_devices.get(acct, set())
        device_changed = 0
        if device_id:
            if device_id not in prev_devices and len(prev_devices) > 0:
                device_changed = 1
            prev_devices.add(device_id)
            account_devices[acct] = prev_devices
        rows.append({
            "account_number": acct,
            "amount": float(tx.get("amount") or 0.0),
            "device_changed": device_changed,
            "geo_abroad": 1 if geo and geo.lower() not in ("india", "in", "local") else 0,
            "is_fraud": is_fraud
        })
    if not rows:
        return pd.DataFrame(columns=["amount", "device_changed", "geo_abroad", "is_fraud"])
    df = pd.DataFrame(rows)
    return df

def estimate_causal_effect(df: pd.DataFrame, treatment: str = "device_changed", outcome: str = "is_fraud") -> Dict[str, Any]:
    """
    Returns: dict with estimated effect, significance, and textual summary.
    Always returns a consistent schema.
    If not enough data, falls back to a synthetic rule-based causal summary.
    """
    # ✅ Lower threshold for demo
    if df.shape[0] < 10:
        return {
            "note": "synthetic_causal_estimate",
            "effect": 0.2,   # pretend device change increases fraud risk by 20%
            "p_value": None,
            "summary": "Based on limited data: device change events are heuristically assumed to raise fraud likelihood by ~20%."
        }

    try:
        model = CausalModel(
            data=df,
            treatment=treatment,
            outcome=outcome,
            common_causes=["amount", "geo_abroad"]
        )
        identified_estimand = model.identify_effect()
        estimate = model.estimate_effect(
            identified_estimand,
            method_name="backdoor.linear_regression"
        )

        effect_value = float(estimate.value) if estimate.value is not None else None

        # Try refutation
        try:
            refute = model.refute_estimate(
                identified_estimand, estimate,
                method_name="placebo_treatment_refuter"
            )
            p_value = getattr(refute, "p_value", None)
        except Exception:
            refute = None
            p_value = None

        return {
            "note": "causal_estimation_success",
            "effect": effect_value,
            "p_value": p_value,
            "estimate_summary": str(estimate),
            "refute": str(refute) if refute else None
        }

    except Exception as e:
        # ✅ Fallback synthetic explanation when DoWhy fails
        return {
            "note": "synthetic_causal_estimate_due_to_error",
            "effect": 0.1,  # pretend baseline effect
            "p_value": None,
            "summary": f"DoWhy failed ({str(e)}). Falling back: transactions abroad + new device assumed to increase fraud risk by ~10%."
        }

