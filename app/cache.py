from __future__ import annotations

import json
import re
from pathlib import Path


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug.strip("_")


class WorkoutCache:
    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir

    @property
    def _workouts_dir(self) -> Path:
        d = self._cache_dir / "workouts"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_connector_payload(
        self, name: str, connector_name: str, payload: dict
    ) -> Path:
        path = self._workouts_dir / f"{_slugify(name)}.{connector_name}.json"
        path.write_text(json.dumps(payload, indent=2))
        return path

    def save_source_plan(self, name: str, content: bytes) -> Path:
        path = self._workouts_dir / f"{_slugify(name)}.source.json"
        path.write_bytes(content)
        return path

    def list_workouts(self) -> list[Path]:
        if not (self._cache_dir / "workouts").exists():
            return []
        return sorted((self._cache_dir / "workouts").iterdir())
