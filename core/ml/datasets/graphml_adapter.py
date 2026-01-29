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

    Each GraphML file represents ONE project.
    """

    if not graphml_path.exists():
        raise FileNotFoundError(f"GraphML file not found: {graphml_path}")

    # 🔑 Project name from file
    project = graphml_path.stem

    graph = nx.read_graphml(graphml_path)

    if not isinstance(graph, nx.DiGraph):
        graph = nx.DiGraph(graph)

    services = list(graph.nodes())

    raw_features = extract_service_features(graph, services)

    scoped_features: Dict[str, Dict[str, float]] = {}

    for service, feats in raw_features.items():
        # 🔑 THIS is the critical fix
        service_id = f"{project}::{service}"

        scoped_features[service_id] = {
            **feats,
            "project": project
        }

    return scoped_features
