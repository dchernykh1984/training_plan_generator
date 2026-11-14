from __future__ import annotations

from typing import Any

import requests

from app.connectors.base import WorkoutConnector
from app.credentials.base import Credentials

# Athlete "0" is whoever owns the API key.
_API_URL = "https://intervals.icu/api/v1/athlete/0"
# Library workouts must live in a folder; uploads go to this one.
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
    """Uploads workouts to an intervals.icu library with a personal API key."""

    def __init__(self) -> None:
        self._session: requests.Session | None = None
        self._folder_id: int | None = None

    @property
    def connector_name(self) -> str:
        return "intervals"

    def login(self, creds: Credentials) -> None:
        session = requests.Session()
        # Personal API key auth: the username is the literal "API_KEY".
        session.auth = ("API_KEY", creds.password)
        # Cloudflare in front of intervals.icu challenges some default client UAs.
        session.headers["User-Agent"] = "training-plan-generator"
        try:
            folder_id = _find_folder_id(_call(session, "GET", "folders"))
            if folder_id is None:
                new_folder = {"name": _FOLDER_NAME, "type": "FOLDER"}
                folder_id = _call(session, "POST", "folders", new_folder)["id"]
        except Exception as e:
            raise RuntimeError(
                f"intervals.icu login failed for {creds.login!r}: {e}"
            ) from e
        self._session = session
        self._folder_id = folder_id

    def upload(self, payload: dict) -> str:
        if self._session is None:
            raise RuntimeError("Not logged in; call login() first")
        body = {**payload, "folder_id": self._folder_id}
        return str(_call(self._session, "POST", "workouts", body)["id"])
