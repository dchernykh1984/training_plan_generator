from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple

from app.models.workout import WorkoutPlan


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
