from __future__ import annotations

import datetime
from typing import Any

import requests

from app.connectors.base import WorkoutConnector
from app.credentials.base import Credentials

# Athlete "0" is whoever owns the API key.
_API_URL = "https://intervals.icu/api/v1/athlete/0"
# The API creates library workouts in a folder or plan; uploads go to this one.
_FOLDER_NAME = "Training Plan Generator"
_TIMEOUT_SECONDS = 30


def _call(
    session: requests.Session, method: str, path: str, body: dict | None = None
) -> Any:
    response = session.request(
        method, f"{_API_URL}/{path}", json=body, timeout=_TIMEOUT_SECONDS
    )
    if not response.ok:
        raise RuntimeError(
            f"intervals.icu {method} {path} failed: HTTP {response.status_code} "
            f"{response.text[:200]}"
        )
    return response.json()


def _find_folder_id(folders: list[dict]) -> int | None:
    for folder in folders:
        if folder.get("type") == "FOLDER" and folder.get("name") == _FOLDER_NAME:
            return folder["id"]
    return None


class IntervalsConnector(WorkoutConnector):
    """Uploads workouts to an intervals.icu account with a personal API key.

    A workout with a day goes on the calendar, from where intervals.icu sends it on
    to the services the athlete connected; one without a day goes to the library.
    """

    def __init__(self) -> None:
        self._session: requests.Session | None = None
        self._folder_id: int | None = None

    @property
    def connector_name(self) -> str:
        return "intervals"

    def login(self, creds: Credentials) -> None:
        session = requests.Session()
        # Personal API key auth: the username is the literal "API_KEY". A key
        # never has whitespace, so a pasted trailing space would only cause a 401.
        session.auth = ("API_KEY", creds.password.strip())
        # Cloudflare in front of intervals.icu challenges some default client UAs.
        session.headers["User-Agent"] = "training-plan-generator"
        try:
            # Reading the folders checks the key without changing anything.
            folder_id = _find_folder_id(_call(session, "GET", "folders"))
        except Exception as e:
            raise RuntimeError(
                f"intervals.icu login failed for {creds.login!r}: {e}"
            ) from e
        self._session = session
        self._folder_id = folder_id

    def upload(self, payload: dict, day: datetime.date | None = None) -> str:
        if self._session is None:
            raise RuntimeError("Not logged in; call login() first")
        if day is not None:
            event = {
                **payload,
                "category": "WORKOUT",
                "start_date_local": f"{day.isoformat()}T00:00:00",
                # The same workout on the same day is updated, not added twice.
                "uid": f"training-plan-generator/{day}/{payload['type']}/"
                f"{payload['name']}",
            }
            path = "events?upsertOnUid=true"
            return str(_call(self._session, "POST", path, event)["id"])
        if self._folder_id is None:
            new_folder = {"name": _FOLDER_NAME, "type": "FOLDER"}
            self._folder_id = _call(self._session, "POST", "folders", new_folder)["id"]
        body = {**payload, "folder_id": self._folder_id}
        return str(_call(self._session, "POST", "workouts", body)["id"])
