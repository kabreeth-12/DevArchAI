from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path

from core.analysis.service_detector import detect_microservices
from core.analysis.dependency_graph import ServiceDependencyGraph
from core.analysis.java_scanner import scan_java_dependencies
from core.analysis.improvement_engine import generate_improvements
from core.analysis.feature_extractor import extract_service_features
from core.ml.inference import DevArchAIInferenceEngine
from core.ml.gnn_inference import DevArchAIGnnInferenceEngine
from core.ml.llm_client import LlmClient
from core.ml.rca_rag import RcaRagEngine

import math

# --------------------------------------------------
# FastAPI App
# --------------------------------------------------

app = FastAPI(title="DevArchAI Core")

# --------------------------------------------------
# Load ML model ONCE at startup
# --------------------------------------------------

inference_engine = DevArchAIInferenceEngine(
    model_path=Path("data/models/devarchai_unified_model.pkl")
)

gnn_inference_engine = None
try:
    gnn_inference_engine = DevArchAIGnnInferenceEngine(
        model_path=Path("data/models/devarchai_gnn_model.pt")
    )
except Exception:
    gnn_inference_engine = None

rca_engine = RcaRagEngine(
    llm_client=LlmClient()
)

# --------------------------------------------------
# API Schemas
# --------------------------------------------------

class AnalyseRequest(BaseModel):
    project_path: str
    log_path: Optional[str] = None
    use_gnn: bool = False


class RiskResult(BaseModel):
    service: str
    predicted_risk_level: int
    risk_confidence: float
    reason: str
    model: Optional[str] = None


class DependencyEdge(BaseModel):
    from_service: str
    to_service: str


class DependencyGraph(BaseModel):
    nodes: List[str]
    edges: List[DependencyEdge]


class AnalyseResponse(BaseModel):
    project_path: str
    detected_services: List[str]
    suspected_root_cause: str
    explanation: str
    rca_summary: str
    rca_confidence: float
    rca_references: List[str]
    rca_llm_used: bool
    risk_analysis: List[RiskResult]
    improvements: List[str]
    dependency_graph: DependencyGraph


def _sanitize_value(value):
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return value
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "DevArchAI backend running",
        "message": "Unified ML-powered backend is live"
    }


# --------------------------------------------------
# Core Analysis Endpoint
# --------------------------------------------------

@app.post("/analyse", response_model=AnalyseResponse)
def analyse_project(request: AnalyseRequest):

    # Step 1: Detect microservices
    services = detect_microservices(request.project_path)

    # Step 2: Build dependency graph
    graph = ServiceDependencyGraph()
    graph.add_services(services)

    project_root = Path(request.project_path)

    # PERFORMANCE GUARD:
    # Analyse all detected services (can be limited later if needed)
    for service in services:
        service_path = project_root / service

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
    if request.use_gnn and gnn_inference_engine is not None:
        risk_analysis = gnn_inference_engine.predict_service_risk(
            graph=graph.graph,
            service_features=service_features
        )
    else:
        risk_analysis = inference_engine.predict_service_risk(
            service_features=service_features
        )

    # Step 5: Generate improvement suggestions
    improvements = generate_improvements(
        services=services,
        dependency_count=len(graph.get_edges())
    )

    # Step 6: Serialize dependency graph for frontend
    dependency_graph = DependencyGraph(
        nodes=graph.get_nodes(),
        edges=[
            DependencyEdge(
                from_service=edge[0],
                to_service=edge[1]
            )
            for edge in graph.get_edges()
        ]
    )

    # Step 7: RCA via RAG + LLM (optional)
    rca_summary = "RCA not available (no log path provided)."
    rca_confidence = 0.0
    rca_references: List[str] = []
    rca_llm_used = False

    if request.log_path:
        try:
            rca_engine.build_index(Path(request.log_path))
            question = (
                f"Identify root cause for service "
                f"{risk_analysis[0]['service'] if risk_analysis else 'unknown'}."
            )
            rca_result = rca_engine.analyse(question=question, top_k=5)
            rca_summary = rca_result.summary
            rca_confidence = rca_result.confidence
            rca_references = rca_result.references
            rca_llm_used = rca_result.llm_used
        except Exception as exc:
            rca_summary = f"RCA failed: {exc}"
            rca_confidence = 0.0
            rca_references = []
            rca_llm_used = False

    # Step 8: Return unified response
    response_payload = AnalyseResponse(
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
        rca_summary=rca_summary,
        rca_confidence=rca_confidence,
        rca_references=rca_references,
        rca_llm_used=rca_llm_used,
        risk_analysis=risk_analysis,
        improvements=improvements,
        dependency_graph=dependency_graph
    )

    # Guard against NaN/Inf in JSON serialization
    return _sanitize_value(response_payload.dict())
