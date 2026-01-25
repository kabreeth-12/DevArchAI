from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from core.analysis.service_detector import detect_microservices
from pathlib import Path
from core.analysis.dependency_graph import ServiceDependencyGraph
from core.analysis.java_scanner import scan_java_dependencies
import time

app = FastAPI(title="DevArchAI Core")


class AnalyseRequest(BaseModel):
    project_path: str


class AnalyseResponse(BaseModel):
    project_path: str
    detected_services: List[str]
    suspected_root_cause: str
    explanation: str


@app.get("/")
def health_check():
    return {
        "status": "DevArchAI backend running",
        "message": "Phase 1 backend is live"
    }


@app.post("/analyse", response_model=AnalyseResponse)
def analyse_project(request: AnalyseRequest):
    services = detect_microservices(request.project_path)

    graph = ServiceDependencyGraph()
    graph.add_services(services)

    project_root = Path(request.project_path)

    # PERFORMANCE GUARD: limit number of services analysed
    for service in services[:5]:
        service_path = project_root / service

        # PERFORMANCE GUARD: Java scan is limited inside this function
        dependencies = scan_java_dependencies(service_path)

        for dep in dependencies:
            if dep in services:
                graph.add_dependency(service, dep)

    return AnalyseResponse(
        project_path=request.project_path,
        detected_services=services,
        suspected_root_cause=services[0] if services else "unknown",
        explanation=(
            f"Dependency graph built with {len(graph.get_edges())} "
            f"inter-service dependencies detected from Java code."
        )
    )
