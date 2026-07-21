"""Behavioural tests for GUI widgets using pytest-qt."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QTabWidget

from app.gui.app import (
    CredentialDialog,
    CredentialsTab,
    MainWindow,
    UploadTab,
    UploadWorker,
    _find_credential,
    make_app_icon,
)
from app.gui.config_store import ConfigStore, CredentialEntry


@pytest.fixture()
def store(tmp_path: Path) -> ConfigStore:
    return ConfigStore(config_dir=tmp_path / "cfg")


_VALID_PLAN = {
    "name": "Morning Ride",
    "sport": "cycling",
    "steps": [{"type": "warmup", "duration_seconds": 300}],
}

_MULTI_PLAN = {
    "morning": {
        "name": "Morning Ride",
        "sport": "cycling",
        "steps": [{"type": "warmup", "duration_seconds": 300}],
    },
    "evening": {
        "name": "Evening Run",
        "sport": "running",
        "steps": [{"type": "cooldown", "duration_seconds": 600}],
    },
}

_GARMIN_CRED = CredentialEntry(
    service="garmin",
    url="https://connect.garmin.com",
    login="me@x",
    password="pw",
)


# ---------------------------------------------------------------------------
# _find_credential
# ---------------------------------------------------------------------------


def test_find_credential_by_service_and_url() -> None:
    entries = [_GARMIN_CRED]
    result = _find_credential(entries, "garmin", "https://connect.garmin.com", None)
    assert result is _GARMIN_CRED


def test_find_credential_not_found_returns_none() -> None:
    entries = [_GARMIN_CRED]
    result = _find_credential(entries, "strava", "https://strava.com", None)
    assert result is None


def test_find_credential_with_login_filter() -> None:
    other = CredentialEntry(
        service="garmin",
        url="https://connect.garmin.com",
        login="other@x",
        password="pw2",
    )
    result = _find_credential(
        [_GARMIN_CRED, other], "garmin", "https://connect.garmin.com", "other@x"
    )
    assert result is other


# ---------------------------------------------------------------------------
# make_app_icon
# ---------------------------------------------------------------------------


def test_make_app_icon_returns_icon(qtbot) -> None:
    icon = make_app_icon()
    assert not icon.isNull()


# ---------------------------------------------------------------------------
# CredentialDialog
# ---------------------------------------------------------------------------


def test_credential_dialog_empty(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    entry = dlg.result_entry()
    assert entry.service == ""
    assert entry.login == ""


def test_credential_dialog_prefilled(qtbot) -> None:
    existing = CredentialEntry(
        "Garmin Connect", "https://connect.garmin.com", "user", "pass"
    )
    dlg = CredentialDialog(entry=existing)
    qtbot.addWidget(dlg)
    entry = dlg.result_entry()
    assert entry.service == "Garmin Connect"
    assert entry.login == "user"
    assert entry.password == "pass"


def test_credential_dialog_password_echo_hidden(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    assert dlg._password.echoMode() == QLineEdit.EchoMode.Password


def test_credential_dialog_ok_disabled_until_service_filled(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    assert not dlg._ok_btn.isEnabled()
    dlg._service.setText("Garmin Connect")
    assert dlg._ok_btn.isEnabled()


def test_credential_dialog_defaults_to_manual(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    assert dlg._manual_radio.isChecked()
    assert not dlg._password.isHidden()
    assert dlg._keepass_row.isHidden()


def test_credential_dialog_service_label_is_account_name(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    labels = [w.text() for w in dlg.findChildren(QLabel)]
    assert "Account name:" in labels


def test_credential_dialog_url_dropdown_has_garmin_preset(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    urls = [dlg._url.itemText(i) for i in range(dlg._url.count())]
    assert "https://connect.garmin.com" in urls
    assert dlg._url.isEditable()


def test_credential_dialog_manual_result(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    dlg._service.setText("Garmin Connect")
    dlg._url.setCurrentText("https://connect.garmin.com")
    dlg._login.setText("me@x")
    dlg._password.setText("secret")
    entry = dlg.result_entry()
    assert entry.source == "manual"
    assert entry.password == "secret"
    assert entry.keepass_path == ""


def test_credential_dialog_keepass_switches_fields(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    dlg._keepass_radio.setChecked(True)
    assert not dlg._keepass_row.isHidden()
    assert dlg._password.isHidden()


def test_credential_dialog_keepass_requires_path(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    dlg._service.setText("Garmin Connect")
    assert dlg._ok_btn.isEnabled()
    dlg._keepass_radio.setChecked(True)
    assert not dlg._ok_btn.isEnabled()
    dlg._keepass_path.setText("/x/db.kdbx")
    assert dlg._ok_btn.isEnabled()


def test_credential_dialog_keepass_result(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    dlg._service.setText("Garmin Connect")
    dlg._url.setCurrentText("https://connect.garmin.com")
    dlg._login.setText("me@x")
    dlg._keepass_radio.setChecked(True)
    dlg._keepass_path.setText("/home/me/db.kdbx")
    entry = dlg.result_entry()
    assert entry.source == "keepass"
    assert entry.keepass_path == "/home/me/db.kdbx"
    assert entry.password == ""


def test_credential_dialog_prefilled_keepass(qtbot) -> None:
    existing = CredentialEntry(
        "Garmin Connect",
        "https://connect.garmin.com",
        "me@x",
        source="keepass",
        keepass_path="/x/db.kdbx",
    )
    dlg = CredentialDialog(entry=existing)
    qtbot.addWidget(dlg)
    assert dlg._keepass_radio.isChecked()
    assert dlg._keepass_path.text() == "/x/db.kdbx"


def test_credential_dialog_browse_keepass_sets_path(qtbot, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog

    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: ("/chosen/db.kdbx", "")
    )
    dlg._browse_keepass()
    assert dlg._keepass_path.text() == "/chosen/db.kdbx"


def test_credential_dialog_browse_keepass_cancel_keeps_path(qtbot, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog

    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    dlg._keepass_path.setText("/existing/db.kdbx")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    dlg._browse_keepass()
    assert dlg._keepass_path.text() == "/existing/db.kdbx"


# ---------------------------------------------------------------------------
# CredentialsTab
# ---------------------------------------------------------------------------


def test_credentials_tab_starts_empty(qtbot, store: ConfigStore) -> None:
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    assert tab._table.rowCount() == 0


def test_credentials_tab_add_credential(qtbot, store: ConfigStore, monkeypatch) -> None:
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)

    new_entry = CredentialEntry("garmin", "https://connect.garmin.com", "me@x", "pw")

    class _AcceptDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_entry(self):
            return new_entry

    monkeypatch.setattr("app.gui.app.CredentialDialog", _AcceptDialog)
    tab._add()
    assert tab._table.rowCount() == 1
    assert store.load_credentials()[0].login == "me@x"


def test_credentials_tab_delete_credential(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    store.save_credentials([_GARMIN_CRED])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    assert tab._table.rowCount() == 1

    tab._table.selectRow(0)
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.question",
        lambda *a, **k: (
            __import__(
                "PySide6.QtWidgets", fromlist=["QMessageBox"]
            ).QMessageBox.StandardButton.Yes
        ),
    )
    tab._delete()
    assert tab._table.rowCount() == 0
    assert store.load_credentials() == []


def test_credentials_tab_edit_noop_on_cancel(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    store.save_credentials([_GARMIN_CRED])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)

    class _RejectDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("app.gui.app.CredentialDialog", _RejectDialog)
    tab._table.selectRow(0)
    tab._edit()
    assert tab._table.rowCount() == 1
    assert store.load_credentials()[0].login == "me@x"


def test_credentials_tab_load_from_file(
    qtbot, store: ConfigStore, monkeypatch, tmp_path: Path
) -> None:
    creds_file = tmp_path / "creds.json"
    creds_file.write_text(
        json.dumps(
            [
                {
                    "service": "garmin",
                    "url": "https://connect.garmin.com",
                    "login": "loaded@x",
                    "password": "pw",
                    "source": "manual",
                }
            ]
        )
    )

    tab = CredentialsTab(store)
    qtbot.addWidget(tab)

    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(creds_file), "")
    )
    tab._load_from_file()
    assert tab._table.rowCount() == 1
    cell = tab._table.item(0, 2)
    assert cell is not None
    assert cell.text() == "loaded@x"


def test_credentials_tab_entries_returns_copy(qtbot, store: ConfigStore) -> None:
    store.save_credentials([_GARMIN_CRED])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    entries = tab.entries()
    assert len(entries) == 1
    entries.clear()
    assert len(tab.entries()) == 1  # original unchanged


# ---------------------------------------------------------------------------
# UploadTab
# ---------------------------------------------------------------------------


def test_upload_tab_loads_single_workout_file(
    qtbot, store: ConfigStore, tmp_path: Path
) -> None:
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(_VALID_PLAN))
    store.save_credentials([_GARMIN_CRED])
    tab = UploadTab(store, CredentialsTab(store))
    qtbot.addWidget(tab)

    tab._plan_path.setText(str(plan_file))
    tab._reload_plan()

    assert tab._workout_combo.count() == 1
    assert "Morning Ride" in tab._workout_combo.currentText()


def test_upload_tab_loads_multi_workout_file(
    qtbot, store: ConfigStore, tmp_path: Path
) -> None:
    plan_file = tmp_path / "multi.json"
    plan_file.write_text(json.dumps(_MULTI_PLAN))
    tab = UploadTab(store, CredentialsTab(store))
    qtbot.addWidget(tab)

    tab._plan_path.setText(str(plan_file))
    tab._reload_plan()

    assert tab._workout_combo.count() == 2


def test_upload_tab_invalid_file_shows_error(
    qtbot, store: ConfigStore, tmp_path: Path
) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json}")
    tab = UploadTab(store, CredentialsTab(store))
    qtbot.addWidget(tab)

    tab._plan_path.setText(str(bad_file))
    tab._reload_plan()

    assert tab._workout_combo.count() == 0
    assert "ERROR" in tab._status.text()


def test_upload_tab_browse_plan_sets_path(
    qtbot, store: ConfigStore, monkeypatch, tmp_path: Path
) -> None:
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(_VALID_PLAN))

    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(plan_file), "")
    )
    tab = UploadTab(store, CredentialsTab(store))
    qtbot.addWidget(tab)
    tab._browse_plan()
    assert tab._plan_path.text() == str(plan_file)
    assert tab._workout_combo.count() == 1


def test_upload_tab_warns_when_no_plan_path(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    warned = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.warning",
        lambda *a, **k: warned.append(a[2]),
    )
    tab = UploadTab(store, CredentialsTab(store))
    qtbot.addWidget(tab)
    tab._plan_path.setText("")
    tab._run_upload()
    assert any("plan" in w.lower() for w in warned)


def test_upload_tab_warns_when_no_credential(
    qtbot, store: ConfigStore, tmp_path: Path, monkeypatch
) -> None:
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(_VALID_PLAN))
    warned = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.warning",
        lambda *a, **k: warned.append(a[2]),
    )
    tab = UploadTab(store, CredentialsTab(store))
    qtbot.addWidget(tab)
    tab._plan_path.setText(str(plan_file))
    tab._reload_plan()
    tab._run_upload()
    assert any("credential" in w.lower() for w in warned)


def test_upload_tab_keepass_paths_needed_for_keepass_cred() -> None:
    cred = CredentialEntry(
        service="garmin",
        url="",
        login="me@x",
        source="keepass",
        keepass_path="/db.kdbx",
    )
    paths = UploadTab._keepass_paths_needed(cred)
    assert paths == ["/db.kdbx"]


def test_upload_tab_keepass_paths_empty_for_manual_cred() -> None:
    cred = CredentialEntry(service="garmin", url="", login="me@x", password="pw")
    paths = UploadTab._keepass_paths_needed(cred)
    assert paths == []


# ---------------------------------------------------------------------------
# UploadWorker
# ---------------------------------------------------------------------------


def test_upload_worker_emits_error_on_missing_file(qtbot, tmp_path: Path) -> None:
    lines: list[str] = []
    results: list[int] = []

    worker = UploadWorker(
        plan_path=str(tmp_path / "nonexistent.json"),
        workout_key=None,
        connector_name="garmin",
        credential_entries=[_GARMIN_CRED],
        keepass_passwords={},
        credential_service="garmin",
        credential_login="me@x",
        cache_dir=tmp_path / "cache",
    )
    worker.log_line.connect(lines.append)
    worker.finished.connect(results.append)

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()
    worker.wait()

    assert results == [1]
    assert any("ERROR" in ln or "error" in ln.lower() for ln in lines)


def test_upload_worker_emits_error_on_missing_credential(qtbot, tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(_VALID_PLAN))
    lines: list[str] = []
    results: list[int] = []

    worker = UploadWorker(
        plan_path=str(plan_file),
        workout_key=None,
        connector_name="garmin",
        credential_entries=[],  # no credentials
        keepass_passwords={},
        credential_service="garmin",
        credential_login="nobody@x",
        cache_dir=tmp_path / "cache",
    )
    worker.log_line.connect(lines.append)
    worker.finished.connect(results.append)

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()
    worker.wait()

    assert results == [1]


def test_upload_worker_success(qtbot, tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(_VALID_PLAN))
    lines: list[str] = []
    results: list[int] = []

    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-99"

    worker = UploadWorker(
        plan_path=str(plan_file),
        workout_key=None,
        connector_name="garmin",
        credential_entries=[_GARMIN_CRED],
        keepass_passwords={},
        credential_service="garmin",
        credential_login="me@x",
        cache_dir=tmp_path / "cache",
    )
    worker.log_line.connect(lines.append)
    worker.finished.connect(results.append)

    with (
        patch("app.connectors.registry.get_connector", return_value=mock_connector),
        qtbot.waitSignal(worker.finished, timeout=5000),
    ):
        worker.start()
    worker.wait()

    assert results == [0]
    assert any("Done" in ln for ln in lines)


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------


def test_main_window_has_upload_and_credentials_tabs(qtbot, store: ConfigStore) -> None:
    win = MainWindow(store)
    qtbot.addWidget(win)
    tabs = win.centralWidget()
    assert isinstance(tabs, QTabWidget)
    labels = [tabs.tabText(i) for i in range(tabs.count())]
    assert "Upload" in labels
    assert "Credentials" in labels


def test_main_window_title(qtbot, store: ConfigStore) -> None:
    win = MainWindow(store)
    qtbot.addWidget(win)
    assert "Training Plan Generator" in win.windowTitle()
