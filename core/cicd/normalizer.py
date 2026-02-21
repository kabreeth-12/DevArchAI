from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from core.cicd.models import StepStatus


_STATUS_MAP = {
    "success": StepStatus.success,
    "succeeded": StepStatus.success,
    "passed": StepStatus.success,
    "ok": StepStatus.success,
    "failure": StepStatus.failure,
    "failed": StepStatus.failure,
    "error": StepStatus.failure,
    "cancelled": StepStatus.cancelled,
    "canceled": StepStatus.cancelled,
    "skipped": StepStatus.skipped,
    "running": StepStatus.running,
    "in_progress": StepStatus.running,
    "queued": StepStatus.running,
    "neutral": StepStatus.neutral,
}


def normalize_status(value: Optional[str]) -> StepStatus:
    if not value:
        return StepStatus.unknown
    key = value.strip().lower()
    return _STATUS_MAP.get(key, StepStatus.unknown)


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        # Assume epoch milliseconds if large, else seconds
        if value > 1_000_000_000_000:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Try ISO 8601
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    return None


def compute_duration_ms(started_at: Optional[datetime], ended_at: Optional[datetime]) -> Optional[int]:
    if not started_at or not ended_at:
        return None
    return int((ended_at - started_at).total_seconds() * 1000)
