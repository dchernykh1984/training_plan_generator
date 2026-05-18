from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class RunLogger:
    def __init__(self, cache_dir: Path) -> None:
        self._log_path = cache_dir / "training_plan_generator.log"
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _write(self, level: str, message: str) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        line = f"{ts} {level} {message}\n"
        with self._log_path.open("a") as f:
            f.write(line)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def warning(self, message: str) -> None:
        self._write("WARNING", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message)
