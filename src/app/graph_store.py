import networkx as nx

# Global in-memory graph
G = nx.Graph()

def add_edge(node1_type: str, node1_id: str, node2_type: str, node2_id: str):
    G.add_node(f"{node1_type}:{node1_id}", type=node1_type)
    G.add_node(f"{node2_type}:{node2_id}", type=node2_type)
    G.add_edge(f"{node1_type}:{node1_id}", f"{node2_type}:{node2_id}")

def neighbors(node_id: str):
    return list(G.neighbors(node_id))

def connected_component(node_id: str):
    """Return connected component containing node_id"""
    if node_id not in G:
        return []
    for comp in nx.connected_components(G):
        if node_id in comp:
            return list(comp)
    return []
