# Build a human-readable explanation from signals
from typing import Dict, Any, List

def synthesize_explanation(account_number: str, tx: Dict[str, Any], rules_score: float, ml_score: float, graph_score: float, causal_summary: Dict[str, Any]) -> str:
    parts: List[str] = []
    parts.append(f"Account {account_number} — Transaction of {tx.get('amount'):.2f} {tx.get('currency', '')}.")
    parts.append(f"Rules score: {rules_score:.2f}; ML anomaly score: {ml_score:.2f}; Graph score: {graph_score:.2f}.")
    final = (0.5*rules_score + 0.15*ml_score + 0.35*graph_score)
    parts.append(f"Combined risk (pre-causal): {final:.2f}.")
    if causal_summary:
        if "effect" in causal_summary and causal_summary["effect"] is not None:
            eff = causal_summary["effect"]
            parts.append(f"Causal analysis suggests treatment effect ≈ {eff:.3f} (positive means increases fraud likelihood).")
        elif causal_summary.get("note"):
            parts.append("Causal analysis note: " + str(causal_summary["note"]))
    # recommended actions
    if final >= 0.75:
        parts.append("Recommended action: BLOCK the transaction and open investigation.")
    elif final >= 0.4:
        parts.append("Recommended action: STEP-UP authentication and manual review.")
    else:
        parts.append("Recommended action: Allow.")
    return " ".join(parts)
