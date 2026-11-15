from __future__ import annotations

import datetime

import garminconnect

from app.connectors.base import WorkoutConnector
from app.credentials.base import Credentials


class GarminConnector(WorkoutConnector):
    def __init__(self) -> None:
        self._client: garminconnect.Garmin | None = None

    @property
    def connector_name(self) -> str:
        return "garmin"

    def login(self, creds: Credentials) -> None:
        try:
            client = garminconnect.Garmin(creds.login, creds.password)
            client.login()
            self._client = client
        except Exception as e:
            raise RuntimeError(f"Garmin login failed for {creds.login!r}: {e}") from e

    def upload(self, payload: dict, day: datetime.date | None = None) -> str:
        if self._client is None:
            raise RuntimeError("Not logged in; call login() first")
        result = self._client.upload_workout(payload)
        workout_id = result.get("workoutId") or result.get("id") or str(result)
        if day is not None:
            try:
                self._client.schedule_workout(workout_id, day.isoformat())
            except Exception as e:
                raise RuntimeError(
                    f"Garmin workout {workout_id} was uploaded but not scheduled "
                    f"for {day}: {e}"
                ) from e
        return str(workout_id)
