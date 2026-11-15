"""Connectors that write each workout as a file into a folder.

Apps without an open upload API still import workout files, so for them the
"upload" is a file in a folder: the app's own one or one the user imports from.
"""

from __future__ import annotations

import base64
import datetime
from collections import Counter
from pathlib import Path

from app.cache import slugify
from app.connectors.base import WorkoutConnector
from app.credentials.base import Credentials


class FolderConnector(WorkoutConnector):
    """Writes ``payload["content"]`` (text) or ``payload["content_base64"]`` to a file.

    There is no account behind a folder, so these connectors need no credentials.
    """

    extension: str
    # True when the connector finds its folder itself, e.g. the app's own one.
    has_default_folder = False

    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder
        self._ready = False
        self._stems: Counter[str] = Counter()

    def default_folder(self) -> Path:
        raise RuntimeError(f"Choose the folder to write {self.extension} files to")

    def login(self, creds: Credentials | None = None) -> None:
        """Check the folder; there is no account to log in to."""
        try:
            folder = self.folder or self.default_folder()
            found = folder.is_dir()
        except OSError as e:
            # e.g. macOS refusing this app access to the Documents folder
            raise RuntimeError(f"Cannot open the folder: {e}") from e
        if not found:
            raise RuntimeError(f"Folder not found: {folder}")
        self.folder = folder
        self._ready = True

    def upload(self, payload: dict, day: datetime.date | None = None) -> str:
        if not self._ready or self.folder is None:
            raise RuntimeError("Folder not checked; call login() first")
        stem = slugify(payload["name"]) or "workout"
        if day is not None:
            stem = f"{day.isoformat()}_{stem}"
        # A second workout of the same name and day in one run gets its own file.
        self._stems[stem] += 1
        if self._stems[stem] > 1:
            stem += f"_{self._stems[stem]}"
        path = self.folder / f"{stem}{self.extension}"
        if "content_base64" in payload:
            path.write_bytes(base64.b64decode(payload["content_base64"]))
        else:
            path.write_text(payload["content"], encoding="utf-8")
        return str(path)
