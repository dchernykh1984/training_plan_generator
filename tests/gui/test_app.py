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
    ResolvedTarget,
    TargetDialog,
    UploadTab,
    UploadWorker,
    _find_credential,
    _keepass_paths,
    _keepass_provider,
    check_credential,
    make_app_icon,
)
from app.gui.config_store import ConfigStore, CredentialEntry, UploadTarget


@pytest.fixture()
def store(tmp_path: Path) -> ConfigStore:
    return ConfigStore(config_dir=tmp_path / "cfg")


_VALID_PLAN = {
    "name": "Morning Ride",
    "sport": "cycling",
    "steps": [{"type": "warmup", "duration_seconds": 300}],
}

_MULTI_PLAN = [
    {
        "name": "Morning Ride",
        "sport": "cycling",
        "steps": [{"type": "warmup", "duration_seconds": 300}],
    },
    {
        "name": "Evening Run",
        "sport": "running",
        "steps": [{"type": "cooldown", "duration_seconds": 600}],
    },
]

_GARMIN_CRED = CredentialEntry(
    service="garmin",
    url="https://connect.garmin.com",
    login="me@x",
    password="pw",
)

_GARMIN_TARGET = UploadTarget(
    connector="garmin",
    credential_service="garmin",
    credential_login="me@x",
)


def _plan_file(tmp_path: Path, data: object, name: str = "plan.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


# ---------------------------------------------------------------------------
# _find_credential
# ---------------------------------------------------------------------------


def test_find_credential_matches_service_and_login() -> None:
    assert _find_credential([_GARMIN_CRED], "garmin", "me@x") is _GARMIN_CRED


def test_find_credential_returns_none_when_absent() -> None:
    assert _find_credential([_GARMIN_CRED], "strava", "me@x") is None


def test_find_credential_distinguishes_logins() -> None:
    other = CredentialEntry(service="garmin", url="", login="other@x", password="pw2")
    assert _find_credential([_GARMIN_CRED, other], "garmin", "other@x") is other


def test_find_credential_does_not_fall_back_on_login_mismatch() -> None:
    """A blank-login target must not silently match a different account."""
    assert _find_credential([_GARMIN_CRED], "garmin", "") is None


# ---------------------------------------------------------------------------
# _keepass_paths
# ---------------------------------------------------------------------------


def test_keepass_paths_deduplicates_same_database() -> None:
    a = CredentialEntry("garmin", "", "a@x", source="keepass", keepass_path="/db.kdbx")
    b = CredentialEntry("garmin", "", "b@x", source="keepass", keepass_path="/db.kdbx")
    assert _keepass_paths([a, b]) == ["/db.kdbx"]


def test_keepass_paths_keeps_distinct_databases_in_order() -> None:
    a = CredentialEntry("garmin", "", "a@x", source="keepass", keepass_path="/one.kdbx")
    b = CredentialEntry("garmin", "", "b@x", source="keepass", keepass_path="/two.kdbx")
    assert _keepass_paths([a, b]) == ["/one.kdbx", "/two.kdbx"]


def test_keepass_paths_ignores_manual_credentials() -> None:
    assert _keepass_paths([_GARMIN_CRED]) == []


# ---------------------------------------------------------------------------
# _keepass_provider
# ---------------------------------------------------------------------------


def test_keepass_provider_reused_within_one_cache() -> None:
    cache: dict = {}
    first = _keepass_provider("/db.kdbx", {"/db.kdbx": "master"}, cache)
    second = _keepass_provider("/db.kdbx", {"/db.kdbx": "master"}, cache)
    assert first is second


def test_keepass_provider_not_shared_between_caches() -> None:
    """A new upload must not reuse a provider built with an earlier password."""
    from app.credentials.keepass import KeePassProvider

    first = _keepass_provider("/db.kdbx", {"/db.kdbx": "wrong"}, {})
    second = _keepass_provider("/db.kdbx", {"/db.kdbx": "correct"}, {})
    assert first is not second
    assert isinstance(second, KeePassProvider)
    assert second._password == "correct"


# ---------------------------------------------------------------------------
# check_credential
# ---------------------------------------------------------------------------


def test_check_credential_manual_ok() -> None:
    ok, message = check_credential(_GARMIN_CRED)
    assert ok
    assert "me@x" in message


def test_check_credential_manual_without_login_fails() -> None:
    ok, message = check_credential(CredentialEntry("garmin", "", "", password="pw"))
    assert not ok
    assert "login" in message.lower()


def test_check_credential_manual_without_password_fails() -> None:
    ok, message = check_credential(CredentialEntry("garmin", "", "me@x"))
    assert not ok
    assert "password" in message.lower()


def test_check_credential_keepass_without_path_fails() -> None:
    entry = CredentialEntry("garmin", "", "me@x", source="keepass")
    ok, message = check_credential(entry)
    assert not ok
    assert "KeePass file" in message


def test_check_credential_keepass_searches_by_title_only(monkeypatch) -> None:
    """The check must not filter on URL, so it reports purely on Title/login."""
    seen = []

    class _Provider:
        def get(self, request):
            seen.append(request)
            from app.credentials.base import Credentials

            return Credentials(login="kp@x", password="s")

    monkeypatch.setattr("app.gui.app._keepass_provider", lambda *a: _Provider())
    entry = CredentialEntry(
        "garmin",
        "https://connect.garmin.com",
        "kp@x",
        source="keepass",
        keepass_path="/db.kdbx",
    )
    ok, message = check_credential(entry, "master")
    assert ok
    assert "kp@x" in message
    assert seen[0].url == ""
    assert seen[0].service == "garmin"


def test_check_credential_keepass_reports_lookup_failure(monkeypatch) -> None:
    class _Provider:
        def get(self, request):
            raise RuntimeError("No KeePass entry found for service='wrong-title'")

    monkeypatch.setattr("app.gui.app._keepass_provider", lambda *a: _Provider())
    entry = CredentialEntry(
        "wrong-title", "", "kp@x", source="keepass", keepass_path="/db.kdbx"
    )
    ok, message = check_credential(entry, "master")
    assert not ok
    assert "No KeePass entry found" in message


# ---------------------------------------------------------------------------
# CredentialsTab - Test button
# ---------------------------------------------------------------------------


def test_credentials_tab_test_button_reports_success(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    store.save_credentials([_GARMIN_CRED])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    tab._table.selectRow(0)

    shown: list[str] = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.information", lambda *a, **k: shown.append(a[2])
    )
    tab._test()
    assert shown and "me@x" in shown[0]


def test_credentials_tab_test_button_reports_failure(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    store.save_credentials([CredentialEntry("garmin", "", "me@x")])  # no password
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    tab._table.selectRow(0)

    warned: list[str] = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.warning", lambda *a, **k: warned.append(a[2])
    )
    tab._test()
    assert warned and "password" in warned[0].lower()


def test_credentials_tab_test_prompts_for_keepass_password(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    kp = CredentialEntry(
        "garmin", "", "kp@x", source="keepass", keepass_path="/db.kdbx"
    )
    store.save_credentials([kp])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    tab._table.selectRow(0)

    passwords: list[str] = []

    class _Provider:
        def get(self, request):
            from app.credentials.base import Credentials

            return Credentials(login="kp@x", password="s")

    def _capture(path, pw_map, cache):
        passwords.append(pw_map[path])
        return _Provider()

    monkeypatch.setattr("app.gui.app._keepass_provider", _capture)
    monkeypatch.setattr(
        "app.gui.app.QInputDialog.getText", lambda *a, **k: ("master", True)
    )
    monkeypatch.setattr("app.gui.app.QMessageBox.information", lambda *a, **k: None)
    tab._test()
    assert passwords == ["master"]


def test_credentials_tab_test_aborts_when_keepass_prompt_cancelled(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    kp = CredentialEntry(
        "garmin", "", "kp@x", source="keepass", keepass_path="/db.kdbx"
    )
    store.save_credentials([kp])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    tab._table.selectRow(0)

    called: list[str] = []
    monkeypatch.setattr(
        "app.gui.app._keepass_provider",
        lambda *a: called.append("built"),
    )
    monkeypatch.setattr("app.gui.app.QInputDialog.getText", lambda *a, **k: ("", False))
    tab._test()
    assert called == []


def test_credentials_tab_test_does_not_prompt_when_keepass_path_missing(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    """A keepass entry with no .kdbx path must fail before asking for a password."""
    store.save_credentials(
        [CredentialEntry("garmin", "", "kp@x", source="keepass", keepass_path="")]
    )
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    tab._table.selectRow(0)

    prompted: list[str] = []
    warned: list[str] = []

    def _fake_get_text(*args, **kwargs) -> tuple[str, bool]:
        prompted.append(args[2])
        return "", True

    monkeypatch.setattr("app.gui.app.QInputDialog.getText", _fake_get_text)
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.warning", lambda *a, **k: warned.append(a[2])
    )
    tab._test()
    assert prompted == []
    assert warned == ["No KeePass file set."]


def test_check_credential_manual_message_says_it_is_unverified() -> None:
    """'Test' must not imply the password was checked against the service."""
    ok, message = check_credential(_GARMIN_CRED)
    assert ok
    assert "not verified" in message.lower()


def test_credentials_tab_test_noop_without_selection(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    store.save_credentials([_GARMIN_CRED])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    tab._table.setCurrentCell(-1, -1)

    shown: list[str] = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.information", lambda *a, **k: shown.append(a[2])
    )
    tab._test()
    assert shown == []


# ---------------------------------------------------------------------------
# make_app_icon
# ---------------------------------------------------------------------------


def test_make_app_icon_returns_icon(qtbot) -> None:
    assert not make_app_icon().isNull()


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


def test_credential_dialog_service_label_says_title_in_keepass_mode(qtbot) -> None:
    """The field is used verbatim as the KeePass Title - the label must say so."""
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    dlg._keepass_radio.setChecked(True)
    assert dlg._service_label.text() == "KeePass entry title:"
    assert "Title" in dlg._service.placeholderText()
    assert "Title" in dlg._service.toolTip()


def test_credential_dialog_service_label_reverts_to_account_name(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    dlg._keepass_radio.setChecked(True)
    dlg._manual_radio.setChecked(True)
    assert dlg._service_label.text() == "Account name:"
    assert dlg._service.placeholderText() == ""


def test_credential_dialog_marks_url_informational_in_keepass_mode(qtbot) -> None:
    dlg = CredentialDialog()
    qtbot.addWidget(dlg)
    assert dlg._url_label.text() == "URL:"
    dlg._keepass_radio.setChecked(True)
    assert "informational" in dlg._url_label.text()


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

    class _AcceptDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_entry(self):
            return _GARMIN_CRED

    monkeypatch.setattr("app.gui.app.CredentialDialog", _AcceptDialog)
    tab._add()
    assert tab._table.rowCount() == 1
    assert store.load_credentials()[0].login == "me@x"


def test_credentials_tab_hides_manual_password_in_table(
    qtbot, store: ConfigStore
) -> None:
    store.save_credentials([_GARMIN_CRED])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    cell = tab._table.item(0, 4)
    assert cell is not None
    assert "pw" not in cell.text()


def test_credentials_tab_delete_credential(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    store.save_credentials([_GARMIN_CRED])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)
    assert tab._table.rowCount() == 1

    tab._table.selectRow(0)
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
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


def test_credentials_tab_double_click_opens_edit(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    store.save_credentials([_GARMIN_CRED])
    tab = CredentialsTab(store)
    qtbot.addWidget(tab)

    class _AcceptDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_entry(self):
            return CredentialEntry("garmin", "", "edited@x", password="pw")

    monkeypatch.setattr("app.gui.app.CredentialDialog", _AcceptDialog)
    tab._table.selectRow(0)
    # Emitting the signal exercises the same path a real double-click takes.
    tab._table.itemDoubleClicked.emit(tab._table.item(0, 0))
    assert store.load_credentials()[0].login == "edited@x"


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
    entries.clear()
    assert len(tab.entries()) == 1


# ---------------------------------------------------------------------------
# TargetDialog
# ---------------------------------------------------------------------------


def test_target_dialog_lists_credentials(qtbot) -> None:
    dlg = TargetDialog([_GARMIN_CRED])
    qtbot.addWidget(dlg)
    assert dlg._credential.count() == 1
    target = dlg.result_target()
    assert target.connector == "garmin"
    assert target.credential_service == "garmin"
    assert target.credential_login == "me@x"


def test_target_dialog_ok_disabled_without_credentials(qtbot) -> None:
    dlg = TargetDialog([])
    qtbot.addWidget(dlg)
    assert dlg.result_target().credential_service == ""


def test_target_dialog_preselects_existing_target(qtbot) -> None:
    other = CredentialEntry(service="garmin", url="", login="other@x", password="p")
    dlg = TargetDialog(
        [_GARMIN_CRED, other],
        target=UploadTarget("garmin", "garmin", "other@x"),
    )
    qtbot.addWidget(dlg)
    assert dlg.result_target().credential_login == "other@x"


# ---------------------------------------------------------------------------
# UploadTab - targets table
# ---------------------------------------------------------------------------


def _upload_tab(qtbot, store: ConfigStore) -> UploadTab:
    tab = UploadTab(store, CredentialsTab(store))
    qtbot.addWidget(tab)
    return tab


def test_upload_tab_starts_with_no_targets(qtbot, store: ConfigStore) -> None:
    assert _upload_tab(qtbot, store)._table.rowCount() == 0


def test_upload_tab_loads_persisted_targets(qtbot, store: ConfigStore) -> None:
    store.save_credentials([_GARMIN_CRED])
    store.save_targets([_GARMIN_TARGET])
    tab = _upload_tab(qtbot, store)
    assert tab._table.rowCount() == 1
    cell = tab._table.item(0, 0)
    assert cell is not None
    assert cell.text() == "garmin"


def test_upload_tab_marks_target_with_missing_credential(
    qtbot, store: ConfigStore
) -> None:
    store.save_targets([_GARMIN_TARGET])  # no credentials saved
    tab = _upload_tab(qtbot, store)
    cell = tab._table.item(0, 1)
    assert cell is not None
    assert "missing" in cell.text()


def test_upload_tab_add_target(qtbot, store: ConfigStore, monkeypatch) -> None:
    store.save_credentials([_GARMIN_CRED])
    tab = _upload_tab(qtbot, store)

    class _AcceptDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_target(self):
            return _GARMIN_TARGET

    monkeypatch.setattr("app.gui.app.TargetDialog", _AcceptDialog)
    tab._add_target()
    assert tab._table.rowCount() == 1
    assert store.load_targets()[0].connector == "garmin"


def test_upload_tab_add_target_warns_without_credentials(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.warning", lambda *a, **k: warned.append(a[2])
    )
    tab = _upload_tab(qtbot, store)
    tab._add_target()
    assert warned
    assert tab._table.rowCount() == 0


def test_upload_tab_delete_target(qtbot, store: ConfigStore) -> None:
    store.save_credentials([_GARMIN_CRED])
    store.save_targets([_GARMIN_TARGET])
    tab = _upload_tab(qtbot, store)
    tab._table.selectRow(0)
    tab._delete_target()
    assert tab._table.rowCount() == 0
    assert store.load_targets() == []


def test_upload_tab_delete_target_noop_without_selection(
    qtbot, store: ConfigStore
) -> None:
    store.save_credentials([_GARMIN_CRED])
    store.save_targets([_GARMIN_TARGET])
    tab = _upload_tab(qtbot, store)
    tab._table.clearSelection()
    tab._table.setCurrentCell(-1, -1)
    tab._delete_target()
    assert tab._table.rowCount() == 1


def test_upload_tab_edit_target(qtbot, store: ConfigStore, monkeypatch) -> None:
    other = CredentialEntry(service="garmin", url="", login="other@x", password="p")
    store.save_credentials([_GARMIN_CRED, other])
    store.save_targets([_GARMIN_TARGET])
    tab = _upload_tab(qtbot, store)

    class _AcceptDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_target(self):
            return UploadTarget("garmin", "garmin", "other@x")

    monkeypatch.setattr("app.gui.app.TargetDialog", _AcceptDialog)
    tab._table.selectRow(0)
    tab._edit_target()
    assert store.load_targets()[0].credential_login == "other@x"


def test_upload_tab_double_click_opens_edit(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    other = CredentialEntry(service="garmin", url="", login="other@x", password="p")
    store.save_credentials([_GARMIN_CRED, other])
    store.save_targets([_GARMIN_TARGET])
    tab = _upload_tab(qtbot, store)

    class _AcceptDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def result_target(self):
            return UploadTarget("garmin", "garmin", "other@x")

    monkeypatch.setattr("app.gui.app.TargetDialog", _AcceptDialog)
    tab._table.selectRow(0)
    tab._table.itemDoubleClicked.emit(tab._table.item(0, 0))
    assert store.load_targets()[0].credential_login == "other@x"


# ---------------------------------------------------------------------------
# UploadTab - plan file and upload guards
# ---------------------------------------------------------------------------


def test_upload_tab_browse_plan_sets_and_persists_path(
    qtbot, store: ConfigStore, monkeypatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QFileDialog

    plan_file = _plan_file(tmp_path, _VALID_PLAN)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(plan_file), "")
    )
    tab = _upload_tab(qtbot, store)
    tab._browse_plan()
    assert tab._plan_path.text() == str(plan_file)
    assert store.load_gui_config().last_plan_path == str(plan_file)


def test_upload_tab_warns_when_no_plan_path(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.warning", lambda *a, **k: warned.append(a[2])
    )
    tab = _upload_tab(qtbot, store)
    tab._plan_path.setText("")
    tab._run_upload()
    assert any("plan" in w.lower() for w in warned)


def test_upload_tab_warns_when_no_targets(
    qtbot, store: ConfigStore, monkeypatch, tmp_path: Path
) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.warning", lambda *a, **k: warned.append(a[2])
    )
    tab = _upload_tab(qtbot, store)
    tab._plan_path.setText(str(_plan_file(tmp_path, _VALID_PLAN)))
    tab._run_upload()
    assert any("target" in w.lower() for w in warned)


def test_upload_tab_warns_when_target_credential_missing(
    qtbot, store: ConfigStore, monkeypatch, tmp_path: Path
) -> None:
    store.save_targets([_GARMIN_TARGET])  # credential was deleted
    warned: list[str] = []
    monkeypatch.setattr(
        "app.gui.app.QMessageBox.warning", lambda *a, **k: warned.append(a[2])
    )
    tab = _upload_tab(qtbot, store)
    tab._plan_path.setText(str(_plan_file(tmp_path, _VALID_PLAN)))
    tab._run_upload()
    assert any("no longer exist" in w for w in warned)
    assert tab._worker is None


def test_upload_tab_resolve_targets_reports_missing(qtbot, store: ConfigStore) -> None:
    store.save_targets([_GARMIN_TARGET])
    tab = _upload_tab(qtbot, store)
    resolved, missing = tab._resolve_targets()
    assert resolved == []
    assert missing == ["garmin / garmin"]


def test_upload_tab_resolve_targets_succeeds(qtbot, store: ConfigStore) -> None:
    store.save_credentials([_GARMIN_CRED])
    store.save_targets([_GARMIN_TARGET])
    tab = _upload_tab(qtbot, store)
    resolved, missing = tab._resolve_targets()
    assert missing == []
    assert resolved[0].credential is not None
    assert resolved[0].credential.login == "me@x"


def test_upload_tab_cancelled_keepass_prompt_aborts_upload(
    qtbot, store: ConfigStore, monkeypatch, tmp_path: Path
) -> None:
    kp_cred = CredentialEntry(
        service="garmin", url="", login="me@x", source="keepass", keepass_path="/d.kdbx"
    )
    store.save_credentials([kp_cred])
    store.save_targets([_GARMIN_TARGET])
    tab = _upload_tab(qtbot, store)
    tab._plan_path.setText(str(_plan_file(tmp_path, _VALID_PLAN)))

    monkeypatch.setattr("app.gui.app.QInputDialog.getText", lambda *a, **k: ("", False))
    tab._run_upload()
    assert tab._worker is None


def test_upload_tab_prompts_once_per_keepass_file(
    qtbot, store: ConfigStore, monkeypatch
) -> None:
    """Two credentials in one .kdbx must trigger a single password prompt."""
    calls: list[str] = []

    def _fake_get_text(*args, **kwargs) -> tuple[str, bool]:
        calls.append(args[2])
        return "secret", True

    monkeypatch.setattr("app.gui.app.QInputDialog.getText", _fake_get_text)
    tab = _upload_tab(qtbot, store)
    a = CredentialEntry("garmin", "", "a@x", source="keepass", keepass_path="/db.kdbx")
    b = CredentialEntry("garmin", "", "b@x", source="keepass", keepass_path="/db.kdbx")
    proceed, passwords = tab._prompt_keepass_passwords(_keepass_paths([a, b]))
    assert proceed
    assert len(calls) == 1
    assert passwords == {"/db.kdbx": "secret"}


# ---------------------------------------------------------------------------
# UploadWorker
# ---------------------------------------------------------------------------


def _run_worker(qtbot, worker: UploadWorker) -> tuple[list[str], list[int]]:
    lines: list[str] = []
    results: list[int] = []
    worker.log_line.connect(lines.append)
    worker.finished.connect(results.append)
    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()
    worker.wait()
    return lines, results


def _worker(plan_path: Path, tmp_path: Path, **kwargs) -> UploadWorker:
    return UploadWorker(
        plan_path=str(plan_path),
        targets=kwargs.pop("targets", [ResolvedTarget("garmin", _GARMIN_CRED)]),
        keepass_passwords=kwargs.pop("keepass_passwords", {}),
        cache_dir=tmp_path / "cache",
    )


def test_upload_worker_errors_on_missing_file(qtbot, tmp_path: Path) -> None:
    lines, results = _run_worker(
        qtbot, _worker(tmp_path / "nonexistent.json", tmp_path)
    )
    assert results == [1]
    assert any("ERROR" in ln for ln in lines)


def test_upload_worker_errors_without_targets(qtbot, tmp_path: Path) -> None:
    plan = _plan_file(tmp_path, _VALID_PLAN)
    lines, results = _run_worker(qtbot, _worker(plan, tmp_path, targets=[]))
    assert results == [1]
    assert any("No upload targets" in ln for ln in lines)


def test_upload_worker_errors_on_invalid_json(qtbot, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json}")
    _, results = _run_worker(qtbot, _worker(bad, tmp_path))
    assert results == [1]


def test_upload_worker_uploads_single_workout(qtbot, tmp_path: Path) -> None:
    plan = _plan_file(tmp_path, _VALID_PLAN)
    connector = MagicMock()
    connector.upload.return_value = "w-1"
    with patch("app.connectors.registry.get_connector", return_value=connector):
        lines, results = _run_worker(qtbot, _worker(plan, tmp_path))
    assert results == [0]
    assert connector.upload.call_count == 1
    assert any("1/1" in ln for ln in lines)


def test_upload_worker_uploads_every_workout_in_file(qtbot, tmp_path: Path) -> None:
    plan = _plan_file(tmp_path, _MULTI_PLAN, "multi.json")
    connector = MagicMock()
    connector.upload.return_value = "w-n"
    with patch("app.connectors.registry.get_connector", return_value=connector):
        lines, results = _run_worker(qtbot, _worker(plan, tmp_path))
    assert results == [0]
    assert connector.upload.call_count == 2
    assert any("2/2" in ln for ln in lines)


def test_upload_worker_logs_in_once_per_target(qtbot, tmp_path: Path) -> None:
    plan = _plan_file(tmp_path, _MULTI_PLAN, "multi.json")
    connector = MagicMock()
    connector.upload.return_value = "w-n"
    with patch("app.connectors.registry.get_connector", return_value=connector):
        _run_worker(qtbot, _worker(plan, tmp_path))
    connector.login.assert_called_once()


def test_upload_worker_uploads_to_every_target(qtbot, tmp_path: Path) -> None:
    plan = _plan_file(tmp_path, _MULTI_PLAN, "multi.json")
    second = CredentialEntry("garmin", "", "two@x", password="pw2")
    targets = [
        ResolvedTarget("garmin", _GARMIN_CRED),
        ResolvedTarget("garmin", second),
    ]
    connector = MagicMock()
    connector.upload.return_value = "w-n"
    with patch("app.connectors.registry.get_connector", return_value=connector):
        _, results = _run_worker(qtbot, _worker(plan, tmp_path, targets=targets))
    assert results == [0]
    assert connector.upload.call_count == 4  # 2 workouts x 2 targets


def test_upload_worker_continues_after_one_workout_fails(qtbot, tmp_path: Path) -> None:
    plan = _plan_file(tmp_path, _MULTI_PLAN, "multi.json")
    connector = MagicMock()
    connector.upload.side_effect = [RuntimeError("boom"), "w-2"]
    with patch("app.connectors.registry.get_connector", return_value=connector):
        _, results = _run_worker(qtbot, _worker(plan, tmp_path))
    assert results == [1]
    assert connector.upload.call_count == 2


def test_upload_worker_login_failure_skips_target(qtbot, tmp_path: Path) -> None:
    plan = _plan_file(tmp_path, _MULTI_PLAN, "multi.json")
    connector = MagicMock()
    connector.login.side_effect = RuntimeError("bad password")
    with patch("app.connectors.registry.get_connector", return_value=connector):
        lines, results = _run_worker(qtbot, _worker(plan, tmp_path))
    assert results == [1]
    connector.upload.assert_not_called()
    assert any("Login" in ln for ln in lines)


def test_upload_worker_caches_payload_per_workout(qtbot, tmp_path: Path) -> None:
    plan = _plan_file(tmp_path, _MULTI_PLAN, "multi.json")
    connector = MagicMock()
    connector.upload.return_value = "w-n"
    with patch("app.connectors.registry.get_connector", return_value=connector):
        _run_worker(qtbot, _worker(plan, tmp_path))
    cached = {p.name for p in (tmp_path / "cache" / "workouts").iterdir()}
    assert any("morning" in n for n in cached)
    assert any("evening" in n for n in cached)


def test_upload_worker_saves_one_source_snapshot_per_run(qtbot, tmp_path: Path) -> None:
    """The whole file is one source artifact, not one copy per workout."""
    plan = _plan_file(tmp_path, _MULTI_PLAN, "multi.json")
    connector = MagicMock()
    connector.upload.return_value = "w-n"
    with patch("app.connectors.registry.get_connector", return_value=connector):
        _run_worker(qtbot, _worker(plan, tmp_path))
    workouts_dir = tmp_path / "cache" / "workouts"
    sources = [p.name for p in workouts_dir.iterdir() if ".source." in p.name]
    assert sources == ["multi.source.json"]


def test_upload_worker_keepass_request_uses_connector_name_as_url(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """A KeePass entry whose URL is shorter than the stored one must still match.

    The provider matches request.url as a substring of the entry URL, so the
    GUI has to send the connector name just like the CLI does.
    """
    from app.credentials.base import CredentialRequest

    seen: list[CredentialRequest] = []

    class _Provider:
        def get(self, request):
            seen.append(request)
            from app.credentials.base import Credentials

            return Credentials(login="kp@x", password="kp-pw")

    monkeypatch.setattr("app.gui.app._keepass_provider", lambda *a: _Provider())

    kp_cred = CredentialEntry(
        service="garmin",
        url="https://connect.garmin.com",
        login="kp@x",
        source="keepass",
        keepass_path="/db.kdbx",
    )
    plan = _plan_file(tmp_path, _VALID_PLAN)
    connector = MagicMock()
    connector.upload.return_value = "w-1"
    with patch("app.connectors.registry.get_connector", return_value=connector):
        _, results = _run_worker(
            qtbot,
            _worker(plan, tmp_path, targets=[ResolvedTarget("garmin", kp_cred)]),
        )

    assert results == [0]
    assert seen[0].url == "garmin"
    assert seen[0].service == "garmin"
    assert seen[0].login == "kp@x"


def test_upload_worker_clears_keepass_passwords_after_run(
    qtbot, tmp_path: Path
) -> None:
    passwords = {"/db.kdbx": "master"}
    worker = _worker(tmp_path / "missing.json", tmp_path, keepass_passwords=passwords)
    _run_worker(qtbot, worker)
    assert passwords == {}


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------


def test_main_window_has_upload_and_credentials_tabs(qtbot, store: ConfigStore) -> None:
    win = MainWindow(store)
    qtbot.addWidget(win)
    tabs = win.centralWidget()
    assert isinstance(tabs, QTabWidget)
    labels = [tabs.tabText(i) for i in range(tabs.count())]
    assert labels == ["Upload", "Credentials"]


def test_main_window_title(qtbot, store: ConfigStore) -> None:
    win = MainWindow(store)
    qtbot.addWidget(win)
    assert "Training Plan Generator" in win.windowTitle()


def test_main_window_refreshes_targets_when_returning_to_upload_tab(
    qtbot, store: ConfigStore
) -> None:
    store.save_targets([_GARMIN_TARGET])
    win = MainWindow(store)
    qtbot.addWidget(win)
    # Credential added after the Upload tab was built.
    win._creds_tab._entries.append(_GARMIN_CRED)
    win._on_tab_changed(0)
    cell = win._upload_tab._table.item(0, 1)
    assert cell is not None
    assert "missing" not in cell.text()
