import datetime

import pytest

from app.adapters.base import AdapterResult, PayloadAdapter
from app.adapters.erg_workout import ErgWorkoutAdapter
from app.adapters.garmin_workout import GarminWorkoutAdapter
from app.adapters.intervals_workout import IntervalsWorkoutAdapter
from app.adapters.zwift_workout import ZwiftWorkoutAdapter
from app.connectors.base import WorkoutConnector
from app.connectors.erg_file import ErgFileConnector
from app.connectors.garmin import GarminConnector
from app.connectors.intervals import IntervalsConnector
from app.connectors.registry import (
    CONNECTORS,
    PAYLOAD_ADAPTERS,
    folder_connector_class,
    get_adapter,
    get_connector,
)
from app.connectors.zwift import ZwiftConnector
from app.credentials.base import Credentials


def test_get_garmin_connector():
    connector = get_connector("garmin")
    assert isinstance(connector, GarminConnector)


def test_get_garmin_adapter():
    adapter = get_adapter("garmin")
    assert isinstance(adapter, GarminWorkoutAdapter)


def test_get_intervals_connector_and_adapter():
    assert isinstance(get_connector("intervals"), IntervalsConnector)
    assert isinstance(get_adapter("intervals"), IntervalsWorkoutAdapter)


def test_get_unknown_connector_raises():
    with pytest.raises(ValueError, match="Unknown connector"):
        get_connector("polar")


def test_get_unknown_adapter_raises():
    with pytest.raises(ValueError, match="Unknown connector"):
        get_adapter("polar")


def test_fake_connector_registered_and_retrieved():
    class FakeConnector(WorkoutConnector):
        @property
        def connector_name(self) -> str:
            return "fake"

        def login(self, creds: Credentials) -> None:
            pass

        def upload(self, payload: dict, day: datetime.date | None = None) -> str:
            return "fake-id"

    CONNECTORS["fake"] = FakeConnector
    try:
        connector = get_connector("fake")
        assert isinstance(connector, FakeConnector)
        assert connector.upload({}) == "fake-id"
    finally:
        del CONNECTORS["fake"]


def test_fake_adapter_registered_and_retrieved():
    from app.models.workout import WorkoutPlan

    class FakeAdapter(PayloadAdapter):
        @property
        def connector_name(self) -> str:
            return "fake"

        def to_payload(self, plan: WorkoutPlan) -> AdapterResult:
            return AdapterResult(payload={"fake": True}, warnings=[])

    PAYLOAD_ADAPTERS["fake"] = FakeAdapter
    try:
        adapter = get_adapter("fake")
        assert isinstance(adapter, FakeAdapter)
        result = adapter.to_payload(None)  # type: ignore[arg-type]
        assert result.payload == {"fake": True}
        assert result.warnings == []
    finally:
        del PAYLOAD_ADAPTERS["fake"]


def test_registries_clean_after_cleanup():
    assert "fake" not in CONNECTORS
    assert "fake" not in PAYLOAD_ADAPTERS


def test_get_zwift_connector_and_adapter():
    assert isinstance(get_connector("zwift"), ZwiftConnector)
    assert isinstance(get_adapter("zwift"), ZwiftWorkoutAdapter)


def test_folder_connector_class_tells_file_connectors_apart():
    assert folder_connector_class("zwift") is ZwiftConnector
    assert folder_connector_class("garmin") is None
    assert folder_connector_class("polar") is None


def test_get_erg_file_connector_and_adapter():
    assert isinstance(get_connector("erg-file"), ErgFileConnector)
    assert isinstance(get_adapter("erg-file"), ErgWorkoutAdapter)
    assert folder_connector_class("erg-file") is ErgFileConnector
