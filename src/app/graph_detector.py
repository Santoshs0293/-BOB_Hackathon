# Produce anomaly scores for account nodes using embeddings + IsolationForest
from sklearn.ensemble import IsolationForest
from typing import Dict, Tuple, List
import numpy as np
from .graph_embedding import train_node_embeddings
import networkx as nx

# cache last-trained embeddings to avoid refit every transaction (in-memory)
_EMBED_CACHE = {"G_version": None, "embeddings": None}

def compute_account_embeddings(G: nx.Graph, embedding_dim: int = 64, refresh: bool = False):
    """
    Returns dictionary of node -> vector for account:* nodes only.
    """
    global _EMBED_CACHE
    # cheap cache using graph size as versioning
    version = (G.number_of_nodes(), G.number_of_edges())
    if _EMBED_CACHE["G_version"] == version and _EMBED_CACHE["embeddings"] is not None and not refresh:
        return _EMBED_CACHE["embeddings"]
    embeddings = train_node_embeddings(G, embedding_dim=embedding_dim, walks_per_node=8, walk_length=30, epochs=3)
    # keep only account nodes
    account_embeddings = {n: np.array(vec, dtype=float) for n, vec in embeddings.items() if n.startswith("account:")}
    _EMBED_CACHE["G_version"] = version
    _EMBED_CACHE["embeddings"] = account_embeddings
    return account_embeddings

def detect_suspicious_accounts(G: nx.Graph, n_estimators: int = 100, contamination: float = 0.02) -> List[Tuple[str, float]]:
    """
    Returns list of (account_node, anomaly_score) sorted descending (most anomalous first).
    anomaly_score is 0..1 where larger means more anomalous.
    """
    account_embeddings = compute_account_embeddings(G)
    if not account_embeddings:
        return []
    nodes = list(account_embeddings.keys())
    X = np.vstack([account_embeddings[n] for n in nodes])
    iso = IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=42)
    iso.fit(X)
    # decision_function: higher is normal, lower is anomalous
    scores = -iso.decision_function(X)  # higher => more anomalous
    # normalize to 0..1
    minv, maxv = float(scores.min()), float(scores.max())
    if maxv - minv <= 1e-9:
        normalized = [0.0 for _ in scores]
    else:
        normalized = [(s - minv) / (maxv - minv) for s in scores]
    results = list(zip(nodes, normalized))
    results.sort(key=lambda x: x[1], reverse=True)
    return results
