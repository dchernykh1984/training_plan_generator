from __future__ import annotations

from abc import ABC, abstractmethod

from app.credentials.base import Credentials


class WorkoutConnector(ABC):
    @property
    @abstractmethod
    def connector_name(self) -> str: ...

    @abstractmethod
    def login(self, creds: Credentials) -> None: ...

    @abstractmethod
    def upload(self, payload: dict) -> str: ...
