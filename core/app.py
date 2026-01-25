from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from pathlib import Path

from core.analysis.service_detector import detect_microservices
from pathlib import Path
from core.analysis.dependency_graph import ServiceDependencyGraph
from core.analysis.java_scanner import scan_java_dependencies
from core.analysis.improvement_engine import generate_improvements
from core.analysis.feature_extractor import extract_service_features
from core.ml.inference import DevArchAIInferenceEngine

app = FastAPI(title="DevArchAI Core")

# -------------------------------
# Load ML model ONCE at startup
# -------------------------------
inference_engine = DevArchAIInferenceEngine(
    model_path=Path("data/models/devarchai_unified_model.pkl")
)

# -------------------------------
# API Schemas
# -------------------------------
class AnalyseRequest(BaseModel):
    project_path: str


class RiskResult(BaseModel):
    service: str
    predicted_risk_level: int
    risk_confidence: float
    reason: str

class AnalyseResponse(BaseModel):
    project_path: str
    detected_services: List[str]
    suspected_root_cause: str
    explanation: str
    risk_analysis: List[RiskResult]
    improvements: List[str]


# -------------------------------
# Health check
# -------------------------------
@app.get("/")
def health_check():
    return {
        "status": "DevArchAI backend running",
        "message": "Unified ML-powered backend is live"
    }


# -------------------------------
# Core analysis endpoint
# -------------------------------
@app.post("/analyse", response_model=AnalyseResponse)
def analyse_project(request: AnalyseRequest):
    # Step 1: Detect microservices
    services = detect_microservices(request.project_path)

    # Step 2: Build dependency graph
    graph = ServiceDependencyGraph()
    graph.add_services(services)

    project_root = Path(request.project_path)

    # PERFORMANCE GUARD:
    # Limit number of services analysed
    for service in services[:5]:
        service_path = project_root / service

        # PERFORMANCE GUARD:
        # Java scanning itself is already limited internally
        dependencies = scan_java_dependencies(service_path)

        for dep in dependencies:
            if dep in services:
                graph.add_dependency(service, dep)

    # Step 3: Extract ML features from dependency graph
    service_features = extract_service_features(
        graph.graph,
        services
    )

    # Step 4: ML-based risk inference
    risk_analysis = inference_engine.predict_service_risk(
        service_features=service_features
    )

    # Step 5: Generate explainable improvement suggestions
    improvements = generate_improvements(
        services=services,
        dependency_count=len(graph.get_edges())
    )

    # Step 6: Return ML-driven response
    return AnalyseResponse(
        project_path=request.project_path,
        detected_services=services,
        suspected_root_cause=(
            risk_analysis[0]["service"] if risk_analysis else "unknown"
        ),
        explanation=(
            "Architectural risk predicted using a unified DevArchAI "
            "machine learning model combining dependency structure, "
            "anomaly signals, and fault impact data."
        ),
        risk_analysis=risk_analysis,
        improvements=improvements
    )
