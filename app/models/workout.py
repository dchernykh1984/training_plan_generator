from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_SPORTS: frozenset[str] = frozenset({"cycling", "running", "swimming"})
SUPPORTED_TARGET_TYPES: frozenset[str] = frozenset({"power", "heart_rate", "cadence"})
SUPPORTED_STEP_TYPES: frozenset[str] = frozenset(
    {"warmup", "cooldown", "interval", "rest"}
)


@dataclass(frozen=True)
class Target:
    type: str
    low: float
    high: float


@dataclass(frozen=True)
class WorkoutStep:
    type: str
    duration_seconds: int
    targets: tuple[Target, ...]


@dataclass(frozen=True)
class RepeatStep:
    count: int
    steps: tuple[WorkoutStep | RepeatStep, ...]


@dataclass(frozen=True)
class WorkoutPlan:
    name: str
    sport: str
    steps: tuple[WorkoutStep | RepeatStep, ...]
