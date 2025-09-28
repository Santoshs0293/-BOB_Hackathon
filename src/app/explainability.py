# src/app/explainability.py
from typing import Dict, Any, List, Optional

def synthesize_explanation(
    account_number: str,
    tx: Dict[str, Any],
    rules_score: float,
    ml_score: float,
    graph_score: float,
    causal_summary: Dict[str, Any],
    top_graph_suspicious: Optional[List] = None
) -> str:
    """
    Produce a human-friendly explanation string.
    If graph suspicion exists, inject a highlighted natural-language sentence.
    """

    parts: List[str] = []
    amount = tx.get("amount", 0.0)
    currency = tx.get("currency", "INR")
    parts.append(f"Account {account_number} — Transaction of {amount:.2f} {currency}.")

    parts.append(f"Rules score: {rules_score:.2f}; ML anomaly score: {ml_score:.2f}; Graph score: {graph_score:.2f}.")

    combined_pre_causal = 0.45 * rules_score + 0.2 * ml_score + 0.35 * graph_score
    parts.append(f"Combined risk (pre-causal): {combined_pre_causal:.2f}.")

    # Graph suspicion highlight: if there are strong entries in top_graph_suspicious
    if top_graph_suspicious and isinstance(top_graph_suspicious, list) and len(top_graph_suspicious) > 0:
        # Build a readable list of top nodes (limit 6)
        labels = []
        # top_graph_suspicious items may be tuples like ("account:123", 1.0)
        for node, score in top_graph_suspicious[:6]:
            labels.append(f"{node} ({score:.2f})")
        # find device mention if any device node present
        device_nodes = [n for n, s in top_graph_suspicious if n.startswith("device:")]
        graph_note = f"⚠️ Graph suspicion due to shared links: {', '.join(labels)}."
        if device_nodes:
            # highlight first device
            dev = device_nodes[0].split(":", 1)[1]
            graph_note = f"⚠️ Graph suspicion due to shared device **{dev}** connecting accounts: {', '.join([n for n, s in top_graph_suspicious if n.startswith('account:')][:6])}."
        parts.append(graph_note)

    # Causal summary: prefer meaningful results, fallback to friendly note
    if causal_summary:
        if causal_summary.get("note") == "not enough data for causal estimation":
            parts.append("Causal analysis note: not enough data for causal estimation.")
        elif causal_summary.get("note") == "estimation_failed":
            parts.append(f"Causal analysis failed: {causal_summary.get('error')}")
        elif "effect" in causal_summary and causal_summary["effect"] is not None:
            eff = causal_summary["effect"]
            parts.append(f"Causal analysis suggests treatment effect ≈ {eff:.3f}.")
        else:
            # fallback synth summary if dowhy returns structured data but no numeric effect
            parts.append("Causal analysis summary: " + str(causal_summary.get("estimate_summary") or causal_summary.get("refute") or causal_summary.get("note") or ""))

    # Final recommended action (based on pre-causal combined score)
    if combined_pre_causal >= 0.75:
        parts.append("Recommended action: BLOCK the transaction and open full investigation.")
    elif combined_pre_causal >= 0.40:
        parts.append("Recommended action: STEP-UP authentication and manual review.")
    else:
        parts.append("Recommended action: Allow.")

    # join with spaces; explanation will be concise but informative
    explanation = " ".join(parts)
    # For demo readability, ensure no double spaces
    return " ".join(explanation.split())
