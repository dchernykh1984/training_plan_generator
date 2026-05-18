from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple

from app.models.workout import WorkoutPlan


class AdapterResult(NamedTuple):
    payload: dict
    warnings: list[str]


class PayloadAdapter(ABC):
    @property
    @abstractmethod
    def connector_name(self) -> str: ...

    @abstractmethod
    def to_payload(self, plan: WorkoutPlan) -> AdapterResult: ...
