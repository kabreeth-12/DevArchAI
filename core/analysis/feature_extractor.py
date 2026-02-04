from typing import Dict, List, Optional
import networkx as nx


def extract_service_features(
    graph: nx.DiGraph,
    services: List[str],
    telemetry_features: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Extract root-cause-oriented features for each service.

    This function generates a unified feature set combining:
    - Graph structural metrics (dependency reasoning)
    - Failure propagation indicators
    - Architectural role heuristics
    - Placeholder observability signals (prototype stage)

    All features align with DevArchAIInferenceEngine.MODEL_FEATURES.
    """

    features: Dict[str, Dict[str, float]] = {}

    # --------------------------------------------------
    # Graph-level metrics (computed once for efficiency)
    # --------------------------------------------------
    degree_centrality = nx.degree_centrality(graph)
    in_degree_centrality = nx.in_degree_centrality(graph)
    out_degree_centrality = nx.out_degree_centrality(graph)
    betweenness_centrality = nx.betweenness_centrality(graph, normalized=True)
    closeness_centrality = nx.closeness_centrality(graph)

    for service in services:
        # Defensive guard
        if service not in graph.nodes:
            graph.add_node(service)


        # --------------------------------------------------
        # Dependency depth (longest downstream chain)
        # --------------------------------------------------
        try:
            depths = nx.single_source_shortest_path_length(graph, service)
            dependency_depth = max(depths.values()) if depths else 0
            reachable_services = max(0, len(depths) - 1)
        except Exception:
            dependency_depth = 0
            reachable_services = 0

        # --------------------------------------------------
        # Architectural role heuristics
        # --------------------------------------------------
        service_lower = service.lower()
        is_gateway = 1.0 if "gateway" in service_lower else 0.0
        is_config_service = 1.0 if "config" in service_lower else 0.0

        # --------------------------------------------------
        # Observability / anomaly placeholders (prototype)
        # --------------------------------------------------
        anomaly_rate = 0.05
        kaggle_anomaly_rate = 0.04
        fault_injection_count = 1.0
        avg_affected_services = max(1.0, float(reachable_services))

        # Composite impact score (interpretable heuristic)
        fault_impact_score = round(
            (
                graph.out_degree(service)
                + betweenness_centrality.get(service, 0.0)
            ) / 5.0,
            3
        )

        # --------------------------------------------------
        # Final unified feature vector
        # --------------------------------------------------
        features[service] = {
            # Structural connectivity
            "fan_in": float(graph.in_degree(service)),
            "fan_out": float(graph.out_degree(service)),

            # Centrality metrics
            "degree_centrality": degree_centrality.get(service, 0.0),
            "in_degree_centrality": in_degree_centrality.get(service, 0.0),
            "out_degree_centrality": out_degree_centrality.get(service, 0.0),
            "betweenness_centrality": betweenness_centrality.get(service, 0.0),
            "closeness_centrality": closeness_centrality.get(service, 0.0),

            # Failure propagation
            "dependency_depth": float(dependency_depth),
            "reachable_services": float(reachable_services),

            # Architectural role signals
            "is_gateway": is_gateway,
            "is_config_service": is_config_service,

            # Observability / RCA signals
            "anomaly_rate": anomaly_rate,
            "kaggle_anomaly_rate": kaggle_anomaly_rate,
            "fault_injection_count": fault_injection_count,
            "avg_affected_services": avg_affected_services,
            "fault_impact_score": fault_impact_score,
        }

        # --------------------------------------------------
        # Telemetry overrides (real signals if available)
        # --------------------------------------------------
        if telemetry_features:
            features[service].update(
                telemetry_features.get(service, {})
            )

    return features
