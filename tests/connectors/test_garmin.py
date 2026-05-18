from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.garmin import GarminConnector
from app.credentials.base import Credentials


def _creds(login="user@test.com", password="pw"):  # noqa: S107
    return Credentials(login=login, password=password)


def _mock_garmin_class(upload_result=None):
    instance = MagicMock()
    instance.login.return_value = None
    instance.upload_workout.return_value = upload_result or {"workoutId": 12345678}
    cls = MagicMock(return_value=instance)
    return cls, instance


def test_login_calls_garmin_with_credentials():
    cls, instance = _mock_garmin_class()
    with patch("app.connectors.garmin.garminconnect.Garmin", cls):
        connector = GarminConnector()
        connector.login(_creds(login="user@test.com", password="secret"))
    cls.assert_called_once_with("user@test.com", "secret")
    instance.login.assert_called_once()


def test_upload_returns_workout_id():
    cls, instance = _mock_garmin_class({"workoutId": 99887766})
    with patch("app.connectors.garmin.garminconnect.Garmin", cls):
        connector = GarminConnector()
        connector.login(_creds())
        workout_id = connector.upload({"workoutName": "Test"})
    assert workout_id == "99887766"
    instance.upload_workout.assert_called_once_with({"workoutName": "Test"})


def test_upload_falls_back_to_id_key():
    cls, _instance = _mock_garmin_class({"id": "abc-123"})
    with patch("app.connectors.garmin.garminconnect.Garmin", cls):
        connector = GarminConnector()
        connector.login(_creds())
        workout_id = connector.upload({})
    assert workout_id == "abc-123"


def test_login_failure_raises_runtime_error():
    cls = MagicMock()
    cls.return_value.login.side_effect = Exception("auth failed")
    with patch("app.connectors.garmin.garminconnect.Garmin", cls):
        connector = GarminConnector()
        with pytest.raises(RuntimeError, match="Garmin login failed"):
            connector.login(_creds())


def test_upload_without_login_raises():
    connector = GarminConnector()
    with pytest.raises(RuntimeError, match="Not logged in"):
        connector.upload({})


def test_connector_name():
    assert GarminConnector().connector_name == "garmin"
