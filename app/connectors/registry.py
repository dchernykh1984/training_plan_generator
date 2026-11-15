from __future__ import annotations

from app.adapters.base import PayloadAdapter
from app.adapters.garmin_workout import GarminWorkoutAdapter
from app.adapters.intervals_workout import IntervalsWorkoutAdapter
from app.adapters.zwift_workout import ZwiftWorkoutAdapter
from app.connectors.base import WorkoutConnector
from app.connectors.folder import FolderConnector
from app.connectors.garmin import GarminConnector
from app.connectors.intervals import IntervalsConnector
from app.connectors.zwift import ZwiftConnector

CONNECTORS: dict[str, type[WorkoutConnector]] = {
    "garmin": GarminConnector,
    "intervals": IntervalsConnector,
    "zwift": ZwiftConnector,
}

PAYLOAD_ADAPTERS: dict[str, type[PayloadAdapter]] = {
    "garmin": GarminWorkoutAdapter,
    "intervals": IntervalsWorkoutAdapter,
    "zwift": ZwiftWorkoutAdapter,
}


def get_connector(connector_name: str) -> WorkoutConnector:
    cls = CONNECTORS.get(connector_name)
    if cls is None:
        supported = sorted(CONNECTORS)
        raise ValueError(
            f"Unknown connector: {connector_name!r}. Supported: {supported}"
        )
    return cls()


def get_adapter(connector_name: str) -> PayloadAdapter:
    cls = PAYLOAD_ADAPTERS.get(connector_name)
    if cls is None:
        supported = sorted(PAYLOAD_ADAPTERS)
        raise ValueError(
            f"Unknown connector: {connector_name!r}. Supported: {supported}"
        )
    return cls()


def folder_connector_class(connector_name: str) -> type[FolderConnector] | None:
    """The class of a connector that writes files, or None for a service one."""
    cls = CONNECTORS.get(connector_name)
    if cls is not None and issubclass(cls, FolderConnector):
        return cls
    return None
