from __future__ import annotations

import os
from pathlib import Path

from app.connectors.folder import FolderConnector


def _workouts_roots() -> list[Path]:
    """Where Zwift keeps custom workouts, in a folder named after the Zwift ID.

    Zwift uses the Documents folder, which Windows may have moved into OneDrive.
    """
    homes = [Path.home()]
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        homes.append(Path(onedrive))
    return [home / "Documents" / "Zwift" / "Workouts" for home in homes]


class ZwiftConnector(FolderConnector):
    """Puts .zwo files into the Zwift custom workouts folder on this computer.

    Zwift syncs that folder to the account the next time it starts.
    """

    extension = ".zwo"
    has_default_folder = True

    @property
    def connector_name(self) -> str:
        return "zwift"

    def default_folder(self) -> Path:
        roots = _workouts_roots()
        accounts = sorted(
            p
            for root in roots
            for p in root.glob("*")
            if p.is_dir() and p.name.isdigit()
        )
        if len(accounts) == 1:
            return accounts[0]
        where = " or ".join(str(root) for root in roots)
        if not accounts:
            raise RuntimeError(
                f"No Zwift workouts folder in {where}; start Zwift once on this "
                "computer or choose the folder"
            )
        ids = ", ".join(p.name for p in accounts)
        raise RuntimeError(f"Several Zwift accounts in {where} ({ids}); choose one")
