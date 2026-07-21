from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "training-plan-generator"

# Single source of truth for supported connectors in the GUI.
# Extend here and in app.py to add new connectors.
CONNECTOR_TYPES: tuple[str, ...] = ("garmin",)


# ---------------------------------------------------------------------------
# GUI data models
# ---------------------------------------------------------------------------


@dataclass
class CredentialEntry:
    """A single credential account.

    "manual" stores the password inline; "keepass" stores only the .kdbx path
    and resolves the password at upload time - the master password is never
    persisted.
    """

    service: str
    url: str
    login: str
    password: str = ""
    source: str = "manual"  # "manual" | "keepass"
    keepass_path: str = ""


@dataclass
class GuiConfig:
    """Last-used upload settings, persisted across sessions."""

    last_plan_path: str = ""
    last_workout_key: str = ""
    last_connector: str = "garmin"
    last_credential_service: str = ""
    last_credential_login: str = ""


# ---------------------------------------------------------------------------
# ConfigStore
# ---------------------------------------------------------------------------


class ConfigStore:
    """Reads and writes GUI config + credentials to a fixed config directory."""

    def __init__(self, config_dir: Path = _DEFAULT_CONFIG_DIR) -> None:
        self._dir = Path(config_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def config_dir(self) -> Path:
        return self._dir

    @property
    def cache_dir(self) -> Path:
        return self._dir / "cache"

    @property
    def credentials_path(self) -> Path:
        return self._dir / "credentials.json"

    @property
    def _config_path(self) -> Path:
        return self._dir / "config.json"

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    def load_credentials(self) -> list[CredentialEntry]:
        if not self.credentials_path.exists():
            return []
        return self.load_credentials_from(self.credentials_path)

    def load_credentials_from(self, path: Path) -> list[CredentialEntry]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("credentials file must contain a JSON array")
        return [_parse_credential_entry(e) for e in raw]

    def save_credentials(self, entries: list[CredentialEntry]) -> None:
        _atomic_write(
            self.credentials_path, [_serialize_credential(e) for e in entries]
        )

    # ------------------------------------------------------------------
    # GUI config
    # ------------------------------------------------------------------

    def load_gui_config(self) -> GuiConfig:
        if not self._config_path.exists():
            return GuiConfig()
        raw: dict = json.loads(self._config_path.read_text(encoding="utf-8"))
        return _parse_gui_config(raw)

    def save_gui_config(self, config: GuiConfig) -> None:
        _atomic_write(
            self._config_path,
            {
                "last_plan_path": config.last_plan_path,
                "last_workout_key": config.last_workout_key,
                "last_connector": config.last_connector,
                "last_credential_service": config.last_credential_service,
                "last_credential_login": config.last_credential_login,
            },
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, data: object) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _parse_credential_entry(raw: dict) -> CredentialEntry:
    return CredentialEntry(
        service=raw["service"],
        url=raw.get("url", ""),
        login=raw.get("login", ""),
        password=raw.get("password", ""),
        source=raw.get("source", "manual"),
        keepass_path=raw.get("keepass_path", ""),
    )


def _serialize_credential(e: CredentialEntry) -> dict:
    d: dict = {
        "service": e.service,
        "url": e.url,
        "login": e.login,
        "source": e.source,
    }
    if e.source == "keepass":
        d["keepass_path"] = e.keepass_path
    else:
        d["password"] = e.password
    return d


def _parse_gui_config(raw: dict) -> GuiConfig:
    return GuiConfig(
        last_plan_path=raw.get("last_plan_path", ""),
        last_workout_key=raw.get("last_workout_key", ""),
        last_connector=raw.get("last_connector", "garmin"),
        last_credential_service=raw.get("last_credential_service", ""),
        last_credential_login=raw.get("last_credential_login", ""),
    )
