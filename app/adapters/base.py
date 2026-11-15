from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple

from app.models.workout import RepeatStep, Target, WorkoutPlan, WorkoutStep

# Apps whose steps are always timed give an open or distance step this length.
FALLBACK_SECONDS = 300


class AdapterResult(NamedTuple):
    payload: dict
    warnings: list[str]


class PayloadAdapter(ABC):
    """Convert a WorkoutPlan to a service-specific upload payload.

    Warning/fallback contract:
    - Unsupported target type: add warning to AdapterResult.warnings, skip target.
    - Unsupported duration_type: add warning, apply a reasonable fallback.
    - Service limit exceeded (e.g. step count): add warning, still attempt upload.
    - Never raise due to unsupported optional parameters if a valid payload can be
      formed; surface the issue as a warning instead.
    """

    @property
    @abstractmethod
    def connector_name(self) -> str: ...

    @abstractmethod
    def to_payload(self, plan: WorkoutPlan) -> AdapterResult: ...


def flatten_steps(steps: tuple[WorkoutStep | RepeatStep, ...]) -> list[WorkoutStep]:
    """The steps in the order they are done, with every repeat written out."""
    flat: list[WorkoutStep] = []
    for step in steps:
        if isinstance(step, RepeatStep):
            flat += flatten_steps(step.steps) * step.count
        else:
            flat.append(step)
    return flat


def timed_seconds(step: WorkoutStep, app_name: str, warnings: list[str]) -> int:
    """The step's length for an app that only has timed steps."""
    if step.duration_type == "time" and step.duration_seconds is not None:
        return step.duration_seconds
    what = "open" if step.duration_seconds is None else f"{step.duration_seconds} m"
    warnings.append(
        f"Step '{step.type}': {app_name} steps are timed; {what} step planned as "
        f"{FALLBACK_SECONDS // 60}m"
    )
    return FALLBACK_SECONDS


def middle(target: Target) -> float:
    """The single value an app that holds one value per step aims for."""
    return (target.low + target.high) / 2
