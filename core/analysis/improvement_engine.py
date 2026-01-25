from typing import List


def generate_improvements(
    services: List[str],
    dependency_count: int
) -> List[str]:
    """
    Generate explainable architecture improvement suggestions
    based on detected structure.
    """

    suggestions = []

    if len(services) > 3:
        suggestions.append(
            "The system contains multiple microservices. "
            "Ensure service boundaries are well-defined to avoid tight coupling."
        )

    if dependency_count == 0:
        suggestions.append(
            "No explicit inter-service dependencies were detected at code level. "
            "This may be due to service discovery or configuration-based routing. "
            "Consider adding runtime tracing or documentation for better visibility."
        )

    if "api-gateway" in " ".join(services).lower():
        suggestions.append(
            "An API Gateway is present and may act as a central entry point. "
            "Monitor gateway load and consider resilience mechanisms to avoid "
            "single points of failure."
        )

    return suggestions
