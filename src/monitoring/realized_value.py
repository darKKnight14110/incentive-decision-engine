"""Rollout gates based on realized outcomes and guardrails."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MonitoringSnapshot:
    cycle: str
    expected_value: float
    realized_value: float | None
    drift_metrics: dict[str,float]
    guardrails: dict[str,float]
    decision: str

def rollout_decision(expected_value: float, realized_value: float | None, guardrails: dict[str,float], thresholds: dict[str,float], ramp: float) -> str:
    if any(value > thresholds.get(name, float("inf")) for name,value in guardrails.items()): return "rollback"
    if realized_value is not None and realized_value < thresholds.get("primary_lower_bound", 0): return "pause"
    if ramp < 1: return "ramp"
    return "continue"
