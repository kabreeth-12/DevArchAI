from typing import Dict, List
import networkx as nx


def extract_service_features(
    graph: nx.DiGraph,
    services: List[str]
) -> Dict[str, Dict[str, float]]:
    """
    Extract root-cause-oriented features for each service.
    These features are used by the DevArchAI ML model.
    """

    features: Dict[str, Dict[str, float]] = {}

    # Graph-level metrics (computed once)
    degree_centrality = nx.degree_centrality(graph)
    in_degree_centrality = nx.in_degree_centrality(graph)
    out_degree_centrality = nx.out_degree_centrality(graph)
    betweenness_centrality = nx.betweenness_centrality(graph, normalized=True)
    closeness_centrality = nx.closeness_centrality(graph)

    for service in services:
        # Defensive defaults
        if service not in graph:
            continue

        # Dependency depth (longest path starting from this service)
        try:
            depth = max(
                len(path) for path in nx.all_simple_paths(graph, source=service)
            )
        except Exception:
            depth = 0

        # Reachability (blast radius)
        reachable = len(nx.descendants(graph, service))

        # Role-based signals
        service_lower = service.lower()
        is_gateway = 1.0 if "gateway" in service_lower else 0.0
        is_config_service = 1.0 if "config" in service_lower else 0.0

        features[service] = {
            # Basic structure
            "fan_in": graph.in_degree(service),
            "fan_out": graph.out_degree(service),

            # Centrality (core RCA signals)
            "degree_centrality": degree_centrality.get(service, 0.0),
            "in_degree_centrality": in_degree_centrality.get(service, 0.0),
            "out_degree_centrality": out_degree_centrality.get(service, 0.0),
            "betweenness_centrality": betweenness_centrality.get(service, 0.0),
            "closeness_centrality": closeness_centrality.get(service, 0.0),

            # Failure propagation
            "dependency_depth": depth,
            "reachable_services": reachable,

            # Architectural roles
            "is_gateway": is_gateway,
            "is_config_service": is_config_service,
        }

    return features
