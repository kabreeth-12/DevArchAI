from __future__ import annotations

from typing import Any, Dict, List

from core.cicd.models import PipelineRun, PipelineStep
from core.cicd.normalizer import compute_duration_ms, normalize_status, parse_datetime


def _extract_jobs(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    jobs = payload.get("jobs")
    if isinstance(jobs, list):
        return jobs
    # Some payloads embed jobs under "workflow_jobs"
    jobs = payload.get("workflow_jobs")
    if isinstance(jobs, dict):
        return jobs.get("jobs", []) or []
    return []


def parse_github_actions(payload: Dict[str, Any]) -> PipelineRun:
    run = payload.get("workflow_run", payload)

    pipeline = PipelineRun(
        provider="github_actions",
        pipeline_id=str(run.get("id")) if run.get("id") is not None else None,
        name=run.get("name") or run.get("display_title"),
        status=normalize_status(run.get("conclusion") or run.get("status")),
        started_at=parse_datetime(run.get("run_started_at")),
        ended_at=parse_datetime(run.get("updated_at") or run.get("completed_at")),
        branch=run.get("head_branch"),
        commit_sha=run.get("head_sha"),
        url=run.get("html_url") or run.get("url"),
        raw_source="github_actions",
    )

    jobs = _extract_jobs(payload)
    steps: List[PipelineStep] = []

    for job in jobs:
        job_steps = job.get("steps") or []
        for step in job_steps:
            started_at = parse_datetime(step.get("started_at"))
            ended_at = parse_datetime(step.get("completed_at"))
            steps.append(
                PipelineStep(
                    name=step.get("name") or "step",
                    status=normalize_status(step.get("conclusion") or step.get("status")),
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=compute_duration_ms(started_at, ended_at),
                )
            )

    pipeline.steps = steps
    pipeline.compute_duration()
    return pipeline
