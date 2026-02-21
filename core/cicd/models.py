from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    success = "success"
    failure = "failure"
    skipped = "skipped"
    running = "running"
    cancelled = "cancelled"
    neutral = "neutral"
    unknown = "unknown"


class PipelineStep(BaseModel):
    name: str
    status: StepStatus = StepStatus.unknown
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    log_snippet: Optional[str] = None


class PipelineRun(BaseModel):
    provider: str
    pipeline_id: Optional[str] = None
    name: Optional[str] = None
    status: StepStatus = StepStatus.unknown
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_duration_ms: Optional[int] = None
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    url: Optional[str] = None
    steps: List[PipelineStep] = Field(default_factory=list)
    raw_source: Optional[str] = None

    def compute_duration(self) -> None:
        if self.started_at and self.ended_at:
            delta = self.ended_at - self.started_at
            self.total_duration_ms = int(delta.total_seconds() * 1000)
