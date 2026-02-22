from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Literal
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
from core.telemetry import fetch_prometheus_metrics, fetch_traces_otel
from core.cicd.loader import load_payload
from core.cicd.github_actions_adapter import parse_github_actions
from core.cicd.gitlab_adapter import parse_gitlab
from core.cicd.jenkins_adapter import parse_jenkins
from core.cicd.optimizer import optimize_pipeline

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
    prometheus_url: Optional[str] = None
    otel_endpoint: Optional[str] = None
    debug_telemetry: bool = False


class CicdIngestRequest(BaseModel):
    provider: Literal["github_actions", "jenkins", "gitlab"]
    source_path: Optional[str] = None
    raw_json: Optional[str] = None


class CicdOptimizeRequest(BaseModel):
    provider: Literal["github_actions", "jenkins", "gitlab"]
    source_path: Optional[str] = None
    raw_json: Optional[str] = None


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
    telemetry_debug: Optional[dict] = None


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
# CI/CD Ingestion Endpoint
# --------------------------------------------------

@app.post("/cicd/ingest")
def ingest_cicd(request: CicdIngestRequest):
    payload = load_payload(
        source_path=request.source_path,
        raw_json=request.raw_json
    )

    if request.provider == "github_actions":
        result = parse_github_actions(payload)
    elif request.provider == "jenkins":
        result = parse_jenkins(payload)
    elif request.provider == "gitlab":
        result = parse_gitlab(payload)
    else:
        return {"error": "Unsupported provider"}

    return result.dict()


# --------------------------------------------------
# CI/CD Optimization Endpoint
# --------------------------------------------------

@app.post("/cicd/optimize")
def optimize_cicd(request: CicdOptimizeRequest):
    payload = load_payload(
        source_path=request.source_path,
        raw_json=request.raw_json
    )

    if request.provider == "github_actions":
        run = parse_github_actions(payload)
    elif request.provider == "jenkins":
        run = parse_jenkins(payload)
    elif request.provider == "gitlab":
        run = parse_gitlab(payload)
    else:
        return {"error": "Unsupported provider"}

    suggestions = optimize_pipeline(run)
    return {
        "provider": run.provider,
        "pipeline_id": run.pipeline_id,
        "suggestions": [s.__dict__ for s in suggestions]
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

    # Step 3: Fetch telemetry (metrics + traces), if configured
    telemetry_features = {}

    if request.prometheus_url:
        try:
            prom = fetch_prometheus_metrics(request.prometheus_url)
            for svc, feats in prom.items():
                telemetry_features.setdefault(svc, {}).update(feats)
        except Exception:
            pass

    if request.otel_endpoint:
        try:
            traces = fetch_traces_otel(request.otel_endpoint)
            for svc, feats in traces.items():
                telemetry_features.setdefault(svc, {}).update(feats)
        except Exception:
            pass

    # Normalize telemetry keys to match detected services
    if telemetry_features:
        normalized = {}
        service_set = set(services)
        for key, value in telemetry_features.items():
            if key in service_set:
                normalized[key] = value
                continue
            prefixed = f"spring-petclinic-{key}"
            if prefixed in service_set:
                normalized[prefixed] = value
                continue
            normalized[key] = value
        telemetry_features = normalized

    # Step 4: Extract ML features from dependency graph + telemetry
    service_features = extract_service_features(
        graph.graph,
        services,
        telemetry_features=telemetry_features
    )

    # Step 5: ML-based risk inference
    if request.use_gnn and gnn_inference_engine is not None:
        risk_analysis = gnn_inference_engine.predict_service_risk(
            graph=graph.graph,
            service_features=service_features
        )
    else:
        risk_analysis = inference_engine.predict_service_risk(
            service_features=service_features
        )

    # Step 6: Normalize model label to unified DevArchAI system
    for item in risk_analysis:
        if isinstance(item, dict):
            item["model"] = "DevArchAI Unified Model"

    # Step 7: Generate improvement suggestions
    improvements = generate_improvements(
        services=services,
        dependency_count=len(graph.get_edges())
    )

    # Step 8: Serialize dependency graph for frontend
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

    # Step 9: RCA via RAG + LLM (optional)
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

    # Step 10: Return unified response
    response_payload = AnalyseResponse(
        project_path=request.project_path,
        detected_services=services,
        suspected_root_cause=(
            risk_analysis[0]["service"] if risk_analysis else "unknown"
        ),
        explanation=(
            "Architectural risk predicted using the DevArchAI Unified Model "
            "that combines dependency structure, telemetry signals, and "
            "fault impact indicators within a single reasoning pipeline."
        ),
        rca_summary=rca_summary,
        rca_confidence=rca_confidence,
        rca_references=rca_references,
        rca_llm_used=rca_llm_used,
        risk_analysis=risk_analysis,
        improvements=improvements,
        dependency_graph=dependency_graph,
        telemetry_debug=(
            telemetry_features if request.debug_telemetry else None
        )
    )

    # Guard against NaN/Inf in JSON serialization
    return _sanitize_value(response_payload.dict())
