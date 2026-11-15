from __future__ import annotations

from pathlib import Path

from app.connectors.folder import FolderConnector

# Zwift reads custom workouts from here, in a folder named after the Zwift ID,
# and syncs them to the account the next time it starts.
_WORKOUTS_ROOT = Path.home() / "Documents" / "Zwift" / "Workouts"


class ZwiftConnector(FolderConnector):
    """Puts .zwo files into the Zwift custom workouts folder on this computer."""

    extension = ".zwo"
    has_default_folder = True

    @property
    def connector_name(self) -> str:
        return "zwift"

    def default_folder(self) -> Path:
        accounts = sorted(
            p for p in _WORKOUTS_ROOT.glob("*") if p.is_dir() and p.name.isdigit()
        )
        if len(accounts) == 1:
            return accounts[0]
        if not accounts:
            raise RuntimeError(
                f"No Zwift workouts folder in {_WORKOUTS_ROOT}; start Zwift once on "
                "this computer or choose the folder"
            )
        ids = ", ".join(p.name for p in accounts)
        raise RuntimeError(
            f"Several Zwift accounts in {_WORKOUTS_ROOT} ({ids}); choose the folder"
        )
