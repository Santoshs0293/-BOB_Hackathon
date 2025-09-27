from typing import Dict, Any
from datetime import datetime
import numpy as np
from sklearn.ensemble import IsolationForest
import networkx as nx
from .graph_detector import detect_suspicious_accounts
from .graph_store import G
from .causal_ai import build_recent_tx_dataframe, estimate_causal_effect
from .explainability import synthesize_explanation

# -----------------------------
# Rule-based scoring
# -----------------------------
def rules_score(tx: Dict[str, Any]) -> float:
    score = 0.0
    amount = abs(tx.get("amount", 0))

    if amount > 100000:
        score += 0.6
    elif amount > 50000:
        score += 0.4
    elif amount > 10000:
        score += 0.2

    hour = tx.get("timestamp").hour if tx.get("timestamp") else None
    if hour is not None and (hour < 5 or hour > 23):
        score += 0.15

    card_present = tx.get("metadata", {}).get("card_present", True)
    if not card_present:
        score += 0.1

    return min(score, 1.0)

# -----------------------------
# ML anomaly detection (Isolation Forest)
# -----------------------------
ISOF_MODEL = None
ISOF_TRAIN_DATA = []

def ml_score(tx: Dict[str, Any]) -> float:
    global ISOF_MODEL, ISOF_TRAIN_DATA
    try:
        hr = tx.get("timestamp").hour if tx.get("timestamp") else 0
        val = [np.log1p(abs(tx.get("amount", 0))), float(hr)]
        ISOF_TRAIN_DATA.append(val)
    except Exception:
        pass

    if ISOF_MODEL is None and len(ISOF_TRAIN_DATA) >= 50:
        ISOF_MODEL = IsolationForest(
            n_estimators=50,
            contamination=0.01,
            random_state=42
        )
        ISOF_MODEL.fit(np.array(ISOF_TRAIN_DATA))

    if ISOF_MODEL is None:
        return 0.0

    X = np.array([[np.log1p(abs(tx.get("amount", 0))),
                   float(tx.get("timestamp").hour if tx.get("timestamp") else 0)]])
    score_raw = -ISOF_MODEL.decision_function(X)[0]
    score = 1/(1 + np.exp(-score_raw))
    return float(min(max(score, 0.0), 1.0))

# -----------------------------
# Graph-based heuristics
# -----------------------------
def graph_heuristic_score(account_number: str, device_id: str = None) -> float:
    from .graph_store import connected_component

    node_key = f"account:{account_number}"
    comp = connected_component(node_key)
    accounts = [n for n in comp if n.startswith("account:")]
    devices = [n for n in comp if n.startswith("device:")]

    score = 0.0
    if len(accounts) >= 3 and len(devices) >= 2:
        score += 0.35
    if len(devices) >= 4:
        score += 0.25
    return min(score, 1.0)

def graph_score_for_account(account_number: str):
    results = detect_suspicious_accounts(G)
    score_map = {n.split(":", 1)[1]: s for n, s in results}
    return score_map.get(account_number, 0.0), results[:10]

# -----------------------------
# Causal analysis
# -----------------------------
async def causal_score_and_summary():
    df = await build_recent_tx_dataframe(limit=400)
    summary = {}
    try:
        s = estimate_causal_effect(df)
        summary = s
    except Exception as e:
        summary = {"note": "causal_failed", "error": str(e)}
    return summary

# -----------------------------
# Graph enrichment features
# -----------------------------
def graph_features(account_number: str):
    node = f"account:{account_number}"
    if not G.has_node(node):
        return {"degree": 0, "betweenness": 0.0}
    return {
        "degree": G.degree(node),
        "betweenness": nx.betweenness_centrality(G).get(node, 0.0)
    }

# -----------------------------
# Full scoring pipeline
# -----------------------------
async def full_score(tx: Dict[str, Any]) -> Dict[str, Any]:
    # rules
    r = rules_score(tx)

    # ml
    m = ml_score(tx)

    # graph
    acct = tx.get("account_number")
    gscore, top_suspicious = graph_score_for_account(acct)
    gfeatures = graph_features(acct)

    # causal
    causal_summary = await causal_score_and_summary()

    # aggregate
    final = min(1.0, 0.45*r + 0.2*m + 0.35*gscore)

    # explanation
    explanation = synthesize_explanation(acct, tx, r, m, gscore, causal_summary)

    verdict = "block" if final >= 0.75 else ("review" if final >= 0.4 else "allow")

    return {
        "score": final,
        "verdict": verdict,
        "explanation": explanation,
        "top_graph_suspicious": top_suspicious,
        "graph_features": gfeatures,
        "causal_summary": causal_summary
    }

# -----------------------------
# Legacy wrappers
# -----------------------------
def aggregate_scores(rules: float, ml: float, graph: float) -> float:
    return min(1.0, 0.45*rules + 0.2*ml + 0.35*graph)

def verdict_from_score(score: float) -> str:
    if score >= 0.75:
        return "block"
    if score >= 0.4:
        return "review"
    return "allow"
