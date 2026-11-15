from __future__ import annotations

from app.connectors.folder import FolderConnector


class ErgFileConnector(FolderConnector):
    """Writes .erg files into a folder, for apps that import them by hand."""

    extension = ".erg"

    @property
    def connector_name(self) -> str:
        return "erg-file"
