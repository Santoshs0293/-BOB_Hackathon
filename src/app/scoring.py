# src/app/scoring.py
from typing import Dict, Any, List, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest
import networkx as nx

# local imports (these modules are part of your project)
from .graph_detector import detect_suspicious_accounts
from .graph_store import G
from .causal_ai import build_recent_tx_dataframe, estimate_causal_effect

# Keep training state in-memory (feedback worker appends)
ISOF_MODEL = None
ISOF_TRAIN_DATA: List[List[float]] = []

# -----------------------------
# Rules
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

    hour = None
    try:
        hour = tx.get("timestamp").hour
    except Exception:
        hour = None
    if hour is not None and (hour < 5 or hour > 23):
        score += 0.15

    card_present = tx.get("metadata", {}).get("card_present", True)
    if not card_present:
        score += 0.1

    return min(score, 1.0)

# -----------------------------
# Isolation Forest ML
# -----------------------------
def ml_score(tx: Dict[str, Any]) -> float:
    global ISOF_MODEL, ISOF_TRAIN_DATA
    try:
        hr = tx.get("timestamp").hour if tx.get("timestamp") else 0
        val = [np.log1p(abs(tx.get("amount", 0))), float(hr)]
        ISOF_TRAIN_DATA.append(val)
    except Exception:
        pass

    if ISOF_MODEL is None and len(ISOF_TRAIN_DATA) >= 50:
        X = np.array(ISOF_TRAIN_DATA)
        ISOF_MODEL = IsolationForest(n_estimators=50, contamination=0.01, random_state=42)
        ISOF_MODEL.fit(X)

    if ISOF_MODEL is None:
        # warm-up: mild anomaly only for very large amounts
        return 0.0 if tx.get("amount", 0) < 20000 else 0.1

    Xq = np.array([[np.log1p(abs(tx.get("amount", 0))),
                    float(tx.get("timestamp").hour if tx.get("timestamp") else 0)]])
    score_raw = -ISOF_MODEL.decision_function(Xq)[0]
    score = 1.0 / (1.0 + np.exp(-score_raw))
    return float(min(max(score, 0.0), 1.0))

# -----------------------------
# Graph heuristics & helpers
# -----------------------------
def graph_heuristic_score(account_number: str) -> float:
    # simple heuristics on connected component
    node_key = f"account:{account_number}"
    if not G.has_node(node_key):
        return 0.0
    comp = list(nx.node_connected_component(G, node_key))
    accounts = [n for n in comp if n.startswith("account:")]
    devices = [n for n in comp if n.startswith("device:")]
    score = 0.0
    if len(accounts) >= 3 and len(devices) >= 2:
        score += 0.35
    if len(devices) >= 4:
        score += 0.25
    return min(score, 1.0)

def graph_score_for_account(account_number: str) -> Tuple[float, List[Tuple[str, float]]]:
    # detect_suspicious_accounts returns list of (node, score) pairs
    try:
        results = detect_suspicious_accounts(G)
    except Exception:
        results = []
    # normalize to list of (node, score) and return top results
    score_map = {n.split(":", 1)[1]: s for n, s in results if ":" in n}
    account_score = score_map.get(account_number, 0.0)
    top = results[:10] if results else []
    return float(account_score), top

def graph_features(account_number: str) -> Dict[str, Any]:
    node = f"account:{account_number}"
    if not G.has_node(node):
        return {"degree": 0, "betweenness": 0.0}
    try:
        bet = nx.betweenness_centrality(G)
        return {"degree": G.degree(node), "betweenness": float(bet.get(node, 0.0))}
    except Exception:
        return {"degree": G.degree(node), "betweenness": 0.0}

# -----------------------------
# Causal analysis wrapper
# -----------------------------
async def causal_score_and_summary() -> Dict[str, Any]:
    try:
        df = await build_recent_tx_dataframe(limit=400)
        summary = estimate_causal_effect(df)
        return summary if summary else {"note": "no_causal_result"}
    except Exception as e:
        return {"note": "causal_failed", "error": str(e)}

# -----------------------------
# Full scoring pipeline
# -----------------------------
async def full_score(tx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run rules -> ML -> graph -> causal (async) and return combined result.
    Returns:
       {
         "score": float,
         "verdict": str,   # fraud / review / allow
         "explanation": str,
         "top_graph_suspicious": [(node, score), ...],
         "graph_features": {...},
         "causal_summary": {...}
       }
    """
    r = rules_score(tx)
    m = ml_score(tx)
    acct = tx.get("account_number")
    gscore, top_graph = graph_score_for_account(acct)
    gfeatures = graph_features(acct)
    causal_summary = await causal_score_and_summary()

    final = min(1.0, 0.45 * r + 0.2 * m + 0.35 * gscore)

    return {
        "score": float(final),
        "verdict": "fraud" if final >= 0.75 else ("review" if final >= 0.4 else "allow"),
        "rules_score": float(r),
        "ml_score": float(m),
        "graph_score": float(gscore),
        "top_graph_suspicious": top_graph,
        "graph_features": gfeatures,
        "causal_summary": causal_summary
    }

# -----------------------------
# Backwards-compatible utilities
# -----------------------------
def aggregate_scores(rules: float, ml: float, graph: float) -> float:
    return min(1.0, 0.45 * rules + 0.2 * ml + 0.35 * graph)

def verdict_from_score(score: float) -> str:
    if score >= 0.75:
        return "fraud"
    if score >= 0.4:
        return "review"
    return "allow"
