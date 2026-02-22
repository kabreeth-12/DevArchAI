from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from core.cicd.models import PipelineRun, PipelineStep


@dataclass
class OptimizationSuggestion:
    title: str
    rationale: str
    impact: str
    action: str


def _step_durations(steps: List[PipelineStep]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for step in steps:
        if step.duration_ms is None:
            continue
        totals[step.name] = totals.get(step.name, 0.0) + float(step.duration_ms)
    return totals


def optimize_pipeline(run: PipelineRun) -> List[OptimizationSuggestion]:
    suggestions: List[OptimizationSuggestion] = []

    if not run.steps:
        return [
            OptimizationSuggestion(
                title="No step data",
                rationale="Pipeline run does not include step timing data.",
                impact="Low",
                action="Enable step-level timing in CI/CD provider and re-run."
            )
        ]

    total_ms = run.total_duration_ms or sum(
        step.duration_ms or 0 for step in run.steps
    )
    if total_ms <= 0:
        total_ms = 1

    step_totals = _step_durations(run.steps)
    sorted_steps = sorted(step_totals.items(), key=lambda x: x[1], reverse=True)

    # Heuristic 1: Slowest step suggestion
    if sorted_steps:
        slowest_name, slowest_ms = sorted_steps[0]
        slowest_ratio = slowest_ms / total_ms
        if slowest_ratio >= 0.4:
            suggestions.append(
                OptimizationSuggestion(
                    title=f"Bottleneck step: {slowest_name}",
                    rationale=f"Step '{slowest_name}' takes {slowest_ratio:.0%} of total pipeline time.",
                    impact="High",
                    action="Enable caching or parallelize this step where possible."
                )
            )

    # Heuristic 2: Test-heavy pipeline
    test_steps = [
        name for name in step_totals
        if "test" in name.lower() or "unit" in name.lower() or "integration" in name.lower()
    ]
    test_time = sum(step_totals[name] for name in test_steps)
    if test_time / total_ms >= 0.5:
        suggestions.append(
            OptimizationSuggestion(
                title="Test suite dominates pipeline",
                rationale="Test steps exceed 50% of total pipeline time.",
                impact="Medium",
                action="Apply test selection or split tests into parallel shards."
            )
        )

    # Heuristic 3: Frequent failure hint
    failed_steps = [s for s in run.steps if s.status.value == "failure"]
    if failed_steps:
        names = sorted({s.name for s in failed_steps})
        suggestions.append(
            OptimizationSuggestion(
                title="Repeated step failures",
                rationale=f"Failed steps detected: {', '.join(names)}.",
                impact="High",
                action="Add retries or isolate flaky tests/build steps."
            )
        )

    # Lightweight RL-style policy (simulated): choose action based on reward proxy
    # Reward proxy: reduce total time + failures
    reward = (1.0 - (len(failed_steps) / max(1, len(run.steps)))) + (1.0 - (max(0.0, slowest_ratio) if sorted_steps else 0.0))
    if reward < 1.0:
        suggestions.append(
            OptimizationSuggestion(
                title="RL policy recommendation",
                rationale="Low reward signal based on failure rate and time dominance.",
                impact="Medium",
                action="Prioritize caching + parallelization in next run; observe reward improvement."
            )
        )

    if not suggestions:
        suggestions.append(
            OptimizationSuggestion(
                title="Pipeline healthy",
                rationale="No dominant bottlenecks or failures detected.",
                impact="Low",
                action="Maintain current pipeline configuration."
            )
        )

    return suggestions
