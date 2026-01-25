from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

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
    """
    Temporary implementation:
    - Accepts a project path
    - Returns mocked analysis
    """

    return AnalyseResponse(
        project_path=request.project_path,
        detected_services=["service-a", "service-b", "service-c"],
        suspected_root_cause="service-b",
        explanation=(
            "Service-b is suspected as the root cause because it is a shared "
            "dependency and failed during the CI/CD build stage."
        )
    )
