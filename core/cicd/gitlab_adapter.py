from __future__ import annotations

from typing import Any, Dict, List

from core.cicd.models import PipelineRun, PipelineStep
from core.cicd.normalizer import compute_duration_ms, normalize_status, parse_datetime


def parse_gitlab(payload: Dict[str, Any]) -> PipelineRun:
    pipeline = PipelineRun(
        provider="gitlab",
        pipeline_id=str(payload.get("id")) if payload.get("id") is not None else None,
        name=payload.get("name") or payload.get("ref"),
        status=normalize_status(payload.get("status")),
        started_at=parse_datetime(payload.get("created_at") or payload.get("started_at")),
        ended_at=parse_datetime(payload.get("updated_at") or payload.get("finished_at")),
        branch=payload.get("ref"),
        commit_sha=payload.get("sha"),
        url=payload.get("web_url"),
        raw_source="gitlab",
    )

    jobs = payload.get("jobs") or payload.get("pipeline_jobs") or []
    steps: List[PipelineStep] = []

    if isinstance(jobs, list):
        for job in jobs:
            started_at = parse_datetime(job.get("started_at"))
            ended_at = parse_datetime(job.get("finished_at"))
            duration_sec = job.get("duration")
            duration_ms = None
            if isinstance(duration_sec, (int, float)):
                duration_ms = int(duration_sec * 1000)
            else:
                duration_ms = compute_duration_ms(started_at, ended_at)

            steps.append(
                PipelineStep(
                    name=job.get("name") or "job",
                    status=normalize_status(job.get("status")),
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=duration_ms,
                )
            )

    pipeline.steps = steps
    pipeline.compute_duration()
    return pipeline
