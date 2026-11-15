from __future__ import annotations

from app.connectors.folder import FolderConnector


class FitFileConnector(FolderConnector):
    """Writes FIT workout files into a folder, e.g. a device's NewFiles folder."""

    extension = ".fit"

    @property
    def connector_name(self) -> str:
        return "fit-file"
