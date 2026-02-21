from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from core.cicd.models import PipelineRun, PipelineStep
from core.cicd.normalizer import compute_duration_ms, normalize_status, parse_datetime


def _extract_stages(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    stages = payload.get("stages")
    if isinstance(stages, list):
        return stages

    # Blue Ocean style: "pipeline" -> "stages"
    pipeline = payload.get("pipeline")
    if isinstance(pipeline, dict):
        stages = pipeline.get("stages")
        if isinstance(stages, list):
            return stages

    return []


def parse_jenkins(payload: Dict[str, Any]) -> PipelineRun:
    started_at = parse_datetime(payload.get("timestamp"))
    duration_ms = payload.get("duration")

    if duration_ms is not None and started_at and not payload.get("endTime"):
        ended_at = started_at + timedelta(milliseconds=duration_ms)
    else:
        ended_at = parse_datetime(payload.get("endTime"))

    pipeline = PipelineRun(
        provider="jenkins",
        pipeline_id=str(payload.get("id")) if payload.get("id") is not None else None,
        name=payload.get("fullDisplayName") or payload.get("name"),
        status=normalize_status(payload.get("result") or payload.get("status")),
        started_at=started_at,
        ended_at=ended_at,
        total_duration_ms=duration_ms if isinstance(duration_ms, int) else None,
        branch=_extract_branch(payload),
        commit_sha=_extract_commit(payload),
        url=payload.get("url"),
        raw_source="jenkins",
    )

    steps: List[PipelineStep] = []
    for stage in _extract_stages(payload):
        stage_started = parse_datetime(stage.get("startTimeMillis"))
        stage_duration = stage.get("durationMillis")
        stage_ended = None
        if stage_started and isinstance(stage_duration, int):
            stage_ended = stage_started + timedelta(milliseconds=stage_duration)

        steps.append(
            PipelineStep(
                name=stage.get("name") or "stage",
                status=normalize_status(stage.get("status") or stage.get("result")),
                started_at=stage_started,
                ended_at=stage_ended,
                duration_ms=stage_duration if isinstance(stage_duration, int) else None,
            )
        )

    pipeline.steps = steps
    pipeline.compute_duration()
    return pipeline


def _extract_branch(payload: Dict[str, Any]) -> str | None:
    actions = payload.get("actions") or []
    for action in actions:
        if not isinstance(action, dict):
            continue
        params = action.get("parameters")
        if isinstance(params, list):
            for p in params:
                if p.get("name") in {"BRANCH_NAME", "branch", "GIT_BRANCH"}:
                    return p.get("value")
    return None


def _extract_commit(payload: Dict[str, Any]) -> str | None:
    actions = payload.get("actions") or []
    for action in actions:
        if not isinstance(action, dict):
            continue
        if "lastBuiltRevision" in action:
            rev = action.get("lastBuiltRevision") or {}
            sha = rev.get("SHA1")
            if sha:
                return sha
    return None
