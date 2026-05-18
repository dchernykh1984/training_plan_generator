from __future__ import annotations

from app.adapters.base import PayloadAdapter
from app.adapters.garmin_workout import GarminWorkoutAdapter
from app.connectors.base import WorkoutConnector
from app.connectors.garmin import GarminConnector

CONNECTORS: dict[str, type[WorkoutConnector]] = {
    "garmin": GarminConnector,
}

PAYLOAD_ADAPTERS: dict[str, type[PayloadAdapter]] = {
    "garmin": GarminWorkoutAdapter,
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
