from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gui.config_store import (
    CONNECTOR_TYPES,
    ConfigStore,
    CredentialEntry,
    GuiConfig,
    UploadTarget,
    _parse_credential_entry,
    _serialize_credential,
)


@pytest.fixture()
def store(tmp_path: Path) -> ConfigStore:
    return ConfigStore(config_dir=tmp_path / "cfg")


# ---------------------------------------------------------------------------
# CONNECTOR_TYPES
# ---------------------------------------------------------------------------


def test_connector_types_contains_garmin() -> None:
    assert "garmin" in CONNECTOR_TYPES


# ---------------------------------------------------------------------------
# CredentialEntry round-trip
# ---------------------------------------------------------------------------


def test_credential_entry_defaults() -> None:
    e = CredentialEntry(service="garmin", url="https://connect.garmin.com", login="me")
    assert e.password == ""
    assert e.source == "manual"
    assert e.keepass_path == ""


def test_serialize_manual_credential() -> None:
    e = CredentialEntry(
        service="garmin",
        url="https://connect.garmin.com",
        login="me@x",
        password="secret",
        source="manual",
    )
    d = _serialize_credential(e)
    assert d["password"] == "secret"
    assert "keepass_path" not in d


def test_serialize_keepass_credential() -> None:
    e = CredentialEntry(
        service="garmin",
        url="https://connect.garmin.com",
        login="me@x",
        source="keepass",
        keepass_path="/home/me/db.kdbx",
    )
    d = _serialize_credential(e)
    assert d["keepass_path"] == "/home/me/db.kdbx"
    assert "password" not in d


def test_parse_credential_entry_minimal() -> None:
    raw = {"service": "garmin", "url": "https://connect.garmin.com", "login": "me@x"}
    e = _parse_credential_entry(raw)
    assert e.source == "manual"
    assert e.password == ""
    assert e.keepass_path == ""


def test_parse_credential_entry_keepass() -> None:
    raw = {
        "service": "garmin",
        "url": "https://connect.garmin.com",
        "login": "me@x",
        "source": "keepass",
        "keepass_path": "/db.kdbx",
    }
    e = _parse_credential_entry(raw)
    assert e.source == "keepass"
    assert e.keepass_path == "/db.kdbx"


# ---------------------------------------------------------------------------
# ConfigStore - credentials
# ---------------------------------------------------------------------------


def test_load_credentials_empty_when_no_file(store: ConfigStore) -> None:
    assert store.load_credentials() == []


def test_save_and_load_credentials_roundtrip(store: ConfigStore) -> None:
    entries = [
        CredentialEntry(
            service="garmin",
            url="https://connect.garmin.com",
            login="me@x",
            password="pw",
        ),
        CredentialEntry(
            service="garmin",
            url="https://connect.garmin.com",
            login="other@x",
            source="keepass",
            keepass_path="/db.kdbx",
        ),
    ]
    store.save_credentials(entries)
    loaded = store.load_credentials()
    assert len(loaded) == 2
    assert loaded[0].login == "me@x"
    assert loaded[1].source == "keepass"


def test_load_credentials_from_file(store: ConfigStore, tmp_path: Path) -> None:
    data = [
        {
            "service": "garmin",
            "url": "https://connect.garmin.com",
            "login": "u@t.com",
            "password": "pw",
            "source": "manual",
        }
    ]
    creds_file = tmp_path / "creds.json"
    creds_file.write_text(json.dumps(data))
    loaded = store.load_credentials_from(creds_file)
    assert len(loaded) == 1
    assert loaded[0].login == "u@t.com"


def test_load_credentials_from_invalid_file_raises(
    store: ConfigStore, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a list"}')
    with pytest.raises(ValueError, match="JSON array"):
        store.load_credentials_from(bad)


# ---------------------------------------------------------------------------
# ConfigStore - GUI config
# ---------------------------------------------------------------------------


def test_load_gui_config_defaults_when_no_file(store: ConfigStore) -> None:
    assert store.load_gui_config().last_plan_path == ""


def test_save_and_load_gui_config_roundtrip(store: ConfigStore) -> None:
    store.save_gui_config(GuiConfig(last_plan_path="/home/user/plan.json"))
    assert store.load_gui_config().last_plan_path == "/home/user/plan.json"


# ---------------------------------------------------------------------------
# ConfigStore - upload targets
# ---------------------------------------------------------------------------


def test_load_targets_empty_when_no_file(store: ConfigStore) -> None:
    assert store.load_targets() == []


def test_save_and_load_targets_roundtrip(store: ConfigStore) -> None:
    targets = [
        UploadTarget(
            connector="garmin", credential_service="garmin", credential_login="me@x"
        ),
        UploadTarget(
            connector="garmin", credential_service="garmin", credential_login="two@x"
        ),
    ]
    store.save_targets(targets)
    loaded = store.load_targets()
    assert len(loaded) == 2
    assert loaded[0].credential_login == "me@x"
    assert loaded[1].credential_login == "two@x"


def test_save_targets_preserves_order(store: ConfigStore) -> None:
    store.save_targets([UploadTarget(credential_login=str(i)) for i in range(4)])
    assert [t.credential_login for t in store.load_targets()] == ["0", "1", "2", "3"]


def test_load_targets_rejects_non_array(store: ConfigStore) -> None:
    store.targets_path.write_text('{"not": "a list"}')
    with pytest.raises(ValueError, match="JSON array"):
        store.load_targets()


def test_target_defaults(store: ConfigStore) -> None:
    store.targets_path.write_text('[{"credential_service": "garmin"}]')
    target = store.load_targets()[0]
    assert target.connector == "garmin"
    assert target.credential_login == ""


def test_save_targets_overwrites_previous(store: ConfigStore) -> None:
    store.save_targets([UploadTarget(credential_service="a")])
    store.save_targets([UploadTarget(credential_service="b")])
    loaded = store.load_targets()
    assert len(loaded) == 1
    assert loaded[0].credential_service == "b"


def test_config_dir_created_on_init(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "new" / "nested"
    store = ConfigStore(config_dir=cfg_dir)
    assert store.config_dir.exists()


def test_cache_dir_property(store: ConfigStore) -> None:
    assert store.cache_dir == store.config_dir / "cache"
