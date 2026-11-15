import datetime
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from app.connectors.intervals import IntervalsConnector
from app.credentials.base import Credentials

_API = "https://intervals.icu/api/v1/athlete/0"
_KEY = "secret-api-key"
_OUR_FOLDER = {"id": 7, "name": "Training Plan Generator", "type": "FOLDER"}


def _response(json_body=None, status=200, text=""):
    response = MagicMock(ok=status < 400, status_code=status, text=text)
    response.json.return_value = json_body
    return response


def _logged_in(*responses, key=_KEY):
    """Log in against a fake Session that answers with ``responses`` in order."""
    session = MagicMock()
    session.headers = {}
    session.request.side_effect = list(responses)
    with patch("app.connectors.intervals.requests.Session", return_value=session):
        connector = IntervalsConnector()
        connector.login(Credentials(login="me@x", password=key))
    return connector, session


def test_login_authenticates_with_the_api_key():
    _, session = _logged_in(_response([_OUR_FOLDER]), key=f" {_KEY}\n")
    assert session.auth == ("API_KEY", _KEY)
    assert session.headers["User-Agent"] == "training-plan-generator"
    session.request.assert_called_once_with(
        "GET", f"{_API}/folders", json=None, timeout=30
    )


def test_upload_goes_to_the_existing_folder_and_returns_the_workout_id():
    connector, session = _logged_in(_response([_OUR_FOLDER]), _response({"id": 42}))

    workout_id = connector.upload({"name": "W", "type": "Ride", "description": "- 1m"})

    assert workout_id == "42"
    assert session.request.call_args == call(
        "POST",
        f"{_API}/workouts",
        json={"name": "W", "type": "Ride", "description": "- 1m", "folder_id": 7},
        timeout=30,
    )


def test_first_library_upload_creates_the_folder_when_missing():
    others = [
        {"id": 1, "name": "Base", "type": "FOLDER"},
        {"id": 2, "name": "Training Plan Generator", "type": "PLAN"},
    ]
    connector, session = _logged_in(
        _response(others), _response({"id": 9}), _response({"id": 5})
    )
    # Logging in only reads the folders, so a calendar-only user gets no folder.
    assert session.request.call_count == 1

    connector.upload({"name": "W"})

    assert session.request.call_args_list[1] == call(
        "POST",
        f"{_API}/folders",
        json={"name": "Training Plan Generator", "type": "FOLDER"},
        timeout=30,
    )
    assert session.request.call_args.kwargs["json"]["folder_id"] == 9


def test_folder_is_created_only_once():
    connector, session = _logged_in(
        _response([]), _response({"id": 9}), _response({"id": 5}), _response({"id": 6})
    )

    connector.upload({"name": "A"})
    connector.upload({"name": "B"})

    posted = [c.args[1] for c in session.request.call_args_list if c.args[0] == "POST"]
    assert posted == [f"{_API}/folders", f"{_API}/workouts", f"{_API}/workouts"]


def test_dated_upload_goes_on_the_calendar_and_updates_a_repeat():
    connector, session = _logged_in(_response([]), _response({"id": 77}))
    payload = {"name": "W", "type": "Ride", "description": "- 1m", "indoor": True}

    event_id = connector.upload(payload, datetime.date(2026, 11, 20))

    assert event_id == "77"
    assert session.request.call_args == call(
        "POST",
        f"{_API}/events?upsertOnUid=true",
        json={
            **payload,
            "category": "WORKOUT",
            "start_date_local": "2026-11-20T00:00:00",
            "uid": "training-plan-generator/2026-11-20/Ride/W",
        },
        timeout=30,
    )


def test_rejected_api_key_fails_login_without_leaking_it():
    with pytest.raises(RuntimeError, match="login failed") as exc_info:
        _logged_in(_response(status=401, text='{"error": "Unauthorized"}'))
    assert "HTTP 401" in str(exc_info.value)
    assert _KEY not in str(exc_info.value)


def test_unexpected_folders_response_fails_login():
    with pytest.raises(RuntimeError, match="login failed"):
        _logged_in(_response({"error": "not a list"}))


def test_network_error_fails_login():
    with pytest.raises(RuntimeError, match="login failed"):
        _logged_in(requests.ConnectionError("unreachable"))


def test_rejected_upload_raises_with_the_server_reason():
    connector, _ = _logged_in(
        _response([_OUR_FOLDER]), _response(status=422, text="bad workout")
    )
    with pytest.raises(RuntimeError, match="HTTP 422 bad workout"):
        connector.upload({"name": "W"})


def test_upload_without_login_raises():
    with pytest.raises(RuntimeError, match="Not logged in"):
        IntervalsConnector().upload({})


def test_connector_name():
    assert IntervalsConnector().connector_name == "intervals"
