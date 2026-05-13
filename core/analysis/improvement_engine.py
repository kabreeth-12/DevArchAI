from typing import Dict, List, Optional


def generate_improvements(
    services: List[str],
    dependency_count: int,
    risk_analysis: Optional[List[dict]] = None,
    service_features: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[str]:
    risk_analysis = risk_analysis or []
    service_features = service_features or {}
    suggestions = []

    high_risk = [r["service"] for r in risk_analysis if r.get("predicted_risk_level") == 2]
    medium_risk = [r["service"] for r in risk_analysis if r.get("predicted_risk_level") == 1]

    # Risk-level-based recommendation
    if high_risk:
        names = ", ".join(high_risk[:3]) + ("..." if len(high_risk) > 3 else "")
        suggestions.append(
            f"{len(high_risk)} service(s) flagged as High risk: {names}. "
            "Add circuit breakers, retry policies, and increase monitoring coverage for these services."
        )
    elif medium_risk:
        names = ", ".join(medium_risk[:3]) + ("..." if len(medium_risk) > 3 else "")
        suggestions.append(
            f"{len(medium_risk)} service(s) at Medium risk: {names}. "
            "Add health-check endpoints and structured logging to improve observability."
        )
    else:
        suggestions.append(
            "No High-risk services detected — structural risk is balanced. "
            "Validate resilience under real fault conditions with chaos engineering (e.g. Chaos Monkey)."
        )

    # Topology-based: flag the highest-centrality node as a potential SPOF
    if service_features:
        top_svc, top_feats = max(
            service_features.items(),
            key=lambda kv: kv[1].get("betweenness_centrality", 0.0)
        )
        bc = top_feats.get("betweenness_centrality", 0.0)
        depth = int(top_feats.get("dependency_depth", 0))
        if bc > 0.01:
            suggestions.append(
                f"{top_svc} has the highest structural centrality in the dependency graph "
                f"(betweenness={bc:.3f}, depth={depth}). "
                "A failure here risks cascading to downstream services — "
                "add a dedicated circuit breaker and health-check SLA."
            )

    # Service mesh recommendation for large systems
    if len(services) >= 15:
        suggestions.append(
            f"{len(services)} microservices detected with {dependency_count} dependency edge(s). "
            "Consider a service mesh (e.g. Istio or Linkerd) for uniform mTLS, "
            "circuit breaking, and distributed tracing across all services."
        )
    elif len(services) > 3:
        suggestions.append(
            "Multiple microservices detected. "
            "Ensure service boundaries are well-defined to avoid tight coupling."
        )

    # Admin-service consolidation
    admin_services = [s for s in services if "admin" in s.lower()]
    if len(admin_services) >= 3:
        shown = ", ".join(admin_services[:3]) + ("..." if len(admin_services) > 3 else "")
        suggestions.append(
            f"{len(admin_services)} admin-facing services detected ({shown}). "
            "Consider consolidating their APIs behind a dedicated admin facade "
            "to reduce cross-cutting concerns."
        )

    # No dependency edges detected
    if dependency_count == 0:
        suggestions.append(
            "No inter-service dependency edges were resolved at code level. "
            "This may indicate runtime-only service discovery. "
            "Add distributed tracing or static dependency documentation "
            "for better architectural visibility."
        )

    # API gateway health
    if "api-gateway" in " ".join(services).lower():
        suggestions.append(
            "An API Gateway is present. "
            "Monitor gateway load and ensure resilience mechanisms are in place "
            "to avoid a single point of failure."
        )

    return suggestions
