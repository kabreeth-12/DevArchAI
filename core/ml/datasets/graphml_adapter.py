from pathlib import Path
from typing import Dict
import networkx as nx

from core.analysis.feature_extractor import extract_service_features


def load_graphml_dataset(
    graphml_path: Path
) -> Dict[str, Dict[str, float]]:
    """
    Load a GraphML microservice dependency graph and
    extract service-level features for ML training.

    Each node in the graph represents a service.
    """

    if not graphml_path.exists():
        raise FileNotFoundError(f"GraphML file not found: {graphml_path}")

    # Load graph
    graph = nx.read_graphml(graphml_path)

    # Ensure directed graph
    if not isinstance(graph, nx.DiGraph):
        graph = nx.DiGraph(graph)

    services = list(graph.nodes())

    # Extract features using DevArchAI feature extractor
    feature_map = extract_service_features(graph, services)

    return feature_map
