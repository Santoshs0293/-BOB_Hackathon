# CPU-friendly node2vec-style embeddings via random walks + gensim Word2Vec
from typing import List
import random
import networkx as nx
from gensim.models import Word2Vec

def generate_random_walks(G: nx.Graph, num_walks_per_node: int = 10, walk_length: int = 40, seed: int = 42) -> List[List[str]]:
    random.seed(seed)
    nodes = list(G.nodes())
    walks = []
    for _ in range(num_walks_per_node):
        random.shuffle(nodes)
        for node in nodes:
            walk = [node]
            while len(walk) < walk_length:
                cur = walk[-1]
                neighbors = list(G.neighbors(cur))
                if not neighbors:
                    break
                walk.append(random.choice(neighbors))
            walks.append(walk)
    return walks

def train_node_embeddings(G: nx.Graph, embedding_dim: int = 64, walks_per_node: int = 10, walk_length: int = 40, window: int = 5, epochs: int = 4):
    """
    Returns: dict {node: vector}
    """
    if G.number_of_nodes() == 0:
        return {}
    walks = generate_random_walks(G, num_walks_per_node=walks_per_node, walk_length=walk_length)
    # gensim expects lists of str tokens
    model = Word2Vec(sentences=walks, vector_size=embedding_dim, window=window, min_count=0, sg=1, workers=1, epochs=epochs)
    embeddings = {}
    for node in G.nodes():
        try:
            embeddings[node] = model.wv[node]
        except KeyError:
            embeddings[node] = [0.0] * embedding_dim
    return embeddings
