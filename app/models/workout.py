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


SUPPORTED_DURATION_TYPES: frozenset[str] = frozenset({"time", "distance", "open"})


@dataclass(frozen=True)
class WorkoutStep:
    type: str
    duration_seconds: int | None
    # Garmin adapter priority when >2 targets: power > heart_rate > cadence
    targets: tuple[Target, ...]
    name: str = ""
    duration_type: str = "time"


@dataclass(frozen=True)
class RepeatStep:
    count: int
    steps: tuple[WorkoutStep | RepeatStep, ...]


@dataclass(frozen=True)
class WorkoutPlan:
    name: str
    sport: str
    steps: tuple[WorkoutStep | RepeatStep, ...]
    description: str = ""
    estimated_tss: float | None = None
    # reserved for percent_ftp target conversion (task 2.8)
    ftp_watts: int | None = None
