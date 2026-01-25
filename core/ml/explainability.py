from typing import Dict, List


RISK_LABEL_MAP = {
    0: "Low",
    1: "Medium",
    2: "High"
}


def explain_service_risk(
    service: str,
    features: Dict[str, float],
    predicted_risk: int
) -> str:
    """
    Generate a human-readable explanation for why
    a service was classified at a given risk level.

    This explanation is aligned with architectural
    reasoning rather than opaque ML internals.
    """

    reasons: List[str] = []

    # Structural dominance
    if features.get("betweenness_centrality", 0) > 0.2:
        reasons.append(
            "high betweenness centrality indicates a potential architectural bottleneck"
        )

    if features.get("fan_in", 0) > 3:
        reasons.append(
            "high fan-in suggests strong coupling with multiple services"
        )

    if features.get("dependency_depth", 0) > 2:
        reasons.append(
            "deep dependency chain increases cascading failure risk"
        )

    # Behavioural signals
    if features.get("anomaly_rate", 0) > 0.1:
        reasons.append(
            "observed runtime anomaly patterns"
        )

    if features.get("kaggle_anomaly_rate", 0) > 0.1:
        reasons.append(
            "log-level anomaly signals detected"
        )

    # Fault impact
    if features.get("fault_impact_score", 0) > 1.0:
        reasons.append(
            "historical fault injection caused widespread service impact"
        )

    # Fallback
    if not reasons:
        reasons.append(
            "combined architectural and behavioural factors"
        )

    risk_label = RISK_LABEL_MAP.get(predicted_risk, "Unknown")

    return (
        f"{risk_label} risk due to " +
        ", ".join(reasons)
    )
