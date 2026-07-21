"""PySide6 GUI for training-plan-generator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.config_store import (
    CONNECTOR_TYPES,
    ConfigStore,
    CredentialEntry,
    GuiConfig,
)

if TYPE_CHECKING:
    from app.credentials.base import CredentialProvider, Credentials
    from app.models.workout import WorkoutPlan
    from app.run_log import RunLogger

_KNOWN_CREDENTIAL_URLS = ("https://connect.garmin.com",)


# ---------------------------------------------------------------------------
# UploadWorker - runs the upload pipeline in a background QThread
# ---------------------------------------------------------------------------


class UploadWorker(QThread):
    log_line = Signal(str)
    finished = Signal(int)  # exit code: 0 = success, 1 = error

    def __init__(
        self,
        plan_path: str,
        workout_key: str | None,
        connector_name: str,
        credential_entries: list[CredentialEntry],
        keepass_passwords: dict[str, str],
        credential_service: str,
        credential_login: str,
        cache_dir: Path,
    ) -> None:
        super().__init__()
        self._plan_path = plan_path
        self._workout_key = workout_key
        self._connector_name = connector_name
        self._credential_entries = credential_entries
        self._keepass_passwords = keepass_passwords
        self._credential_service = credential_service
        self._credential_login = credential_login or None
        self._cache_dir = cache_dir
        self._source_bytes: bytes | None = None
        self._kp_providers: dict[str, CredentialProvider] = {}

    def run(self) -> None:
        try:
            rc = self._upload()
        except Exception as exc:
            self.log_line.emit(f"[ERROR] Unexpected error: {exc}")
            rc = 1
        finally:
            # Drop the master passwords as soon as this upload is over.
            self._keepass_passwords.clear()
            self._kp_providers.clear()
        self.finished.emit(rc)

    # ------------------------------------------------------------------
    # Upload pipeline
    # ------------------------------------------------------------------

    def _upload(self) -> int:
        import logging

        from app.cache import WorkoutCache
        from app.connectors.registry import get_adapter, get_connector
        from app.run_log import RunLogger

        log = RunLogger(self._cache_dir)
        cache = WorkoutCache(self._cache_dir)

        plan = self._load_plan(log)
        if plan is None:
            return 1

        self.log_line.emit(f"Building {self._connector_name} payload...")
        adapter = get_adapter(self._connector_name)
        adapt_result = adapter.to_payload(plan)
        for w in adapt_result.warnings:
            self.log_line.emit(f"[WARNING] {w}")
            log.warning(w)
        payload = adapt_result.payload

        creds = self._get_creds(log)
        if creds is None:
            return 1

        self.log_line.emit(f"Logging in to {self._connector_name} ({creds.login})...")
        connector = get_connector(self._connector_name)
        garmin_logger = logging.getLogger("garminconnect.client")
        orig_level = garmin_logger.level
        garmin_logger.setLevel(logging.ERROR)
        try:
            connector.login(creds)
        except RuntimeError as exc:
            self.log_line.emit(f"[ERROR] Login: {exc}")
            log.error(f"login error: {exc}")
            return 1
        finally:
            garmin_logger.setLevel(orig_level)

        log.info("login success")
        self.log_line.emit(f'Uploading "{plan.name}"...')
        try:
            workout_id = connector.upload(payload)
        except Exception as exc:
            self.log_line.emit(f"[ERROR] Upload: {exc}")
            log.error(f"upload error: {exc}")
            return 1

        log.info(f"upload success: id={workout_id}")
        payload_path = cache.save_connector_payload(
            plan.name, self._connector_name, payload
        )
        cache.save_source_plan(plan.name, self._source_bytes or b"")
        self.log_line.emit(f"Done. Cached payload: {payload_path}")
        self.log_line.emit(f"Log: {self._cache_dir / 'training_plan_generator.log'}")
        return 0

    def _load_plan(self, log: RunLogger) -> WorkoutPlan | None:
        from app.models.parser import parse_workout_file

        self.log_line.emit(f"Loading plan: {Path(self._plan_path).name}")
        try:
            source_bytes = Path(self._plan_path).read_bytes()
        except OSError as exc:
            self.log_line.emit(f"[ERROR] {exc}")
            log.error(f"plan read error: {exc}")
            return None
        self._source_bytes = source_bytes

        try:
            plans = parse_workout_file(json.loads(source_bytes))
        except (ValueError, json.JSONDecodeError) as exc:
            self.log_line.emit(f"[ERROR] {exc}")
            log.error(f"parse error: {exc}")
            return None

        if self._workout_key is not None and self._workout_key in plans:
            plan = plans[self._workout_key]
        elif len(plans) == 1:
            plan = next(iter(plans.values()))
        else:
            self.log_line.emit(
                f"[ERROR] Multiple workouts; select one: {sorted(plans)}"
            )
            return None

        self.log_line.emit(
            f"Plan loaded: {plan.name!r} ({plan.sport}, {len(plan.steps)} steps)"
        )
        log.info(
            f"plan loaded: name={plan.name!r} sport={plan.sport} "
            f"steps={len(plan.steps)}"
        )
        return plan

    def _get_creds(self, log: RunLogger) -> Credentials | None:
        from app.credentials.base import (
            CredentialRequest,
            Credentials,
            CredentialsNotFoundError,
        )

        self.log_line.emit("Reading credentials...")
        request = CredentialRequest(
            service=self._credential_service or self._connector_name,
            url=self._connector_name,
            login=self._credential_login,
        )
        entry = _find_credential(
            self._credential_entries,
            request.service,
            request.url,
            request.login,
        )
        try:
            if entry is None:
                raise CredentialsNotFoundError(
                    f"No credential found for service={request.service!r}"
                )
            if entry.source == "keepass":
                provider = _keepass_provider(
                    entry.keepass_path, self._keepass_passwords, self._kp_providers
                )
                kp_request = CredentialRequest(
                    service=request.service,
                    url=entry.url or request.url,
                    login=entry.login or request.login,
                )
                return provider.get(kp_request)
            return Credentials(login=entry.login, password=entry.password)
        except Exception as exc:
            self.log_line.emit(f"[ERROR] Credentials: {exc}")
            log.error(f"credentials error: {exc}")
            return None


def _find_credential(
    entries: list[CredentialEntry], service: str, url: str, login: str | None
) -> CredentialEntry | None:
    matches = [
        e
        for e in entries
        if e.service == service
        and (not url or url in e.url or e.url in url or not e.url)
        and (login is None or e.login == login)
    ]
    return matches[0] if matches else None


def _keepass_provider(
    path: str,
    passwords: dict[str, str],
    cache: dict[str, CredentialProvider],
) -> CredentialProvider:
    """Build (or reuse) a KeePass provider for ``path``.

    ``cache`` is owned by a single UploadWorker, so one master password is
    requested per .kdbx file per upload and is discarded once that upload
    finishes - it is never held in a module-level global.
    """
    if path not in cache:
        from app.credentials.keepass import KeePassProvider

        cache[path] = KeePassProvider(
            path=Path(path).expanduser(),
            password=passwords.get(path, ""),
        )
    return cache[path]


# ---------------------------------------------------------------------------
# CredentialDialog
# ---------------------------------------------------------------------------


class CredentialDialog(QDialog):
    def __init__(
        self,
        entry: CredentialEntry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Credential" if entry is None else "Edit Credential")
        self.setMinimumWidth(440)

        form = QFormLayout(self)

        src_row = QHBoxLayout()
        self._manual_radio = QRadioButton("Enter manually")
        self._keepass_radio = QRadioButton("From KeePass file")
        src_row.addWidget(self._manual_radio)
        src_row.addWidget(self._keepass_radio)
        src_row.addStretch()
        form.addRow("Source:", src_row)

        self._service = QLineEdit(entry.service if entry else "")
        self._url = QComboBox()
        self._url.setEditable(True)
        self._url.addItems(list(_KNOWN_CREDENTIAL_URLS))
        self._url.setCurrentText(entry.url if entry else "")
        self._login = QLineEdit(entry.login if entry else "")
        form.addRow("Account name:", self._service)
        form.addRow("URL:", self._url)
        form.addRow("Login:", self._login)

        self._password = QLineEdit(entry.password if entry else "")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_label = QLabel("Password / Token:")
        form.addRow(self._password_label, self._password)

        kp_row = QHBoxLayout()
        self._keepass_path = QLineEdit(entry.keepass_path if entry else "")
        self._keepass_path.setPlaceholderText("Path to .kdbx file")
        self._keepass_browse = QPushButton("Browse...")
        kp_row.addWidget(self._keepass_path)
        kp_row.addWidget(self._keepass_browse)
        self._keepass_row = QWidget()
        self._keepass_row.setLayout(kp_row)
        self._keepass_label = QLabel("KeePass file:")
        form.addRow(self._keepass_label, self._keepass_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

        self._ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        self._service.textChanged.connect(self._validate)
        self._keepass_path.textChanged.connect(self._validate)
        self._keepass_radio.toggled.connect(self._on_source_changed)
        self._keepass_browse.clicked.connect(self._browse_keepass)

        is_keepass = entry is not None and entry.source == "keepass"
        self._keepass_radio.setChecked(is_keepass)
        self._manual_radio.setChecked(not is_keepass)
        self._on_source_changed()

    def _on_source_changed(self) -> None:
        is_keepass = self._keepass_radio.isChecked()
        self._password.setVisible(not is_keepass)
        self._password_label.setVisible(not is_keepass)
        self._keepass_row.setVisible(is_keepass)
        self._keepass_label.setVisible(is_keepass)
        self._validate()

    def _browse_keepass(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Select KeePass database", "", "KeePass (*.kdbx);;All files (*)"
        )
        if path_str:
            self._keepass_path.setText(path_str)

    def _validate(self) -> None:
        ok = bool(self._service.text().strip())
        if self._keepass_radio.isChecked():
            ok = ok and bool(self._keepass_path.text().strip())
        self._ok_btn.setEnabled(ok)

    def result_entry(self) -> CredentialEntry:
        if self._keepass_radio.isChecked():
            return CredentialEntry(
                service=self._service.text().strip(),
                url=self._url.currentText().strip(),
                login=self._login.text().strip(),
                source="keepass",
                keepass_path=self._keepass_path.text().strip(),
            )
        return CredentialEntry(
            service=self._service.text().strip(),
            url=self._url.currentText().strip(),
            login=self._login.text().strip(),
            password=self._password.text(),
            source="manual",
        )


# ---------------------------------------------------------------------------
# CredentialsTab
# ---------------------------------------------------------------------------


class CredentialsTab(QWidget):
    def __init__(self, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._entries: list[CredentialEntry] = store.load_credentials()

        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Service", "URL", "Login", "Source", "Secret / KeePass file"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add")
        self._edit_btn = QPushButton("Edit")
        self._delete_btn = QPushButton("Delete")
        self._load_btn = QPushButton("Load from file...")
        for btn in (self._add_btn, self._edit_btn, self._delete_btn):
            btn_row.addWidget(btn)
        btn_row.addStretch()
        btn_row.addWidget(self._load_btn)
        layout.addLayout(btn_row)

        self._add_btn.clicked.connect(self._add)
        self._edit_btn.clicked.connect(self._edit)
        self._delete_btn.clicked.connect(self._delete)
        self._load_btn.clicked.connect(self._load_from_file)
        self._table.itemDoubleClicked.connect(self._edit)

        self._refresh_table()

    def _load_from_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Load credentials", "", "JSON files (*.json);;All files (*)"
        )
        if not path_str:
            return
        try:
            entries = self._store.load_credentials_from(Path(path_str))
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.critical(
                self, "Load failed", f"Could not load credentials:\n{exc}"
            )
            return
        self._entries = entries
        self._store.save_credentials(self._entries)
        self._refresh_table()

    def _refresh_table(self) -> None:
        self._table.setRowCount(0)
        for entry in self._entries:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(entry.service))
            self._table.setItem(row, 1, QTableWidgetItem(entry.url))
            self._table.setItem(row, 2, QTableWidgetItem(entry.login))
            self._table.setItem(row, 3, QTableWidgetItem(entry.source))
            detail = entry.keepass_path if entry.source == "keepass" else "*" * 8
            self._table.setItem(row, 4, QTableWidgetItem(detail))

    def _add(self) -> None:
        dlg = CredentialDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._entries.append(dlg.result_entry())
            self._store.save_credentials(self._entries)
            self._refresh_table()

    def _edit(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        dlg = CredentialDialog(entry=self._entries[row], parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._entries[row] = dlg.result_entry()
        self._store.save_credentials(self._entries)
        self._refresh_table()

    def _delete(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        entry = self._entries[row]
        reply = QMessageBox.question(
            self,
            "Delete credential",
            f"Delete credential for {entry.service!r}?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._entries.pop(row)
            self._store.save_credentials(self._entries)
            self._refresh_table()

    def entries(self) -> list[CredentialEntry]:
        return list(self._entries)


# ---------------------------------------------------------------------------
# UploadTab
# ---------------------------------------------------------------------------


class UploadTab(QWidget):
    def __init__(
        self,
        store: ConfigStore,
        creds_tab: CredentialsTab,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._creds_tab = creds_tab
        self._config: GuiConfig = store.load_gui_config()
        self._plans: dict[str, WorkoutPlan] = {}
        self._worker: UploadWorker | None = None

        root = QVBoxLayout(self)

        # Plan file group
        plan_box = QGroupBox("Plan file")
        plan_form = QFormLayout(plan_box)
        plan_row = QHBoxLayout()
        self._plan_path = QLineEdit(self._config.last_plan_path)
        self._plan_path.setPlaceholderText("Path to workout JSON file")
        self._plan_browse = QPushButton("Browse...")
        self._plan_reload = QPushButton("Reload")
        plan_row.addWidget(self._plan_path)
        plan_row.addWidget(self._plan_browse)
        plan_row.addWidget(self._plan_reload)
        plan_form.addRow("File:", plan_row)

        self._workout_combo = QComboBox()
        self._workout_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        plan_form.addRow("Workout:", self._workout_combo)
        root.addWidget(plan_box)

        # Upload settings group
        settings_box = QGroupBox("Upload settings")
        settings_form = QFormLayout(settings_box)

        self._connector_combo = QComboBox()
        self._connector_combo.addItems(list(CONNECTOR_TYPES))
        idx = self._connector_combo.findText(self._config.last_connector)
        if idx >= 0:
            self._connector_combo.setCurrentIndex(idx)
        settings_form.addRow("Connector:", self._connector_combo)

        self._cred_combo = QComboBox()
        self._cred_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        settings_form.addRow("Credential:", self._cred_combo)

        root.addWidget(settings_box)

        # Upload button
        btn_row = QHBoxLayout()
        self._upload_btn = QPushButton("Upload")
        self._upload_btn.setFixedHeight(36)
        btn_row.addWidget(self._upload_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Status / log
        self._status = QLabel("Ready")
        root.addWidget(self._status)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        root.addWidget(self._log)

        # Wire signals
        self._plan_browse.clicked.connect(self._browse_plan)
        self._plan_reload.clicked.connect(self._reload_plan)
        self._plan_path.editingFinished.connect(self._reload_plan)
        self._upload_btn.clicked.connect(self._run_upload)

        self._refresh_credential_combo()
        if self._config.last_plan_path:
            self._reload_plan()

    def _browse_plan(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Select workout plan", "", "JSON files (*.json);;All files (*)"
        )
        if path_str:
            self._plan_path.setText(path_str)
            self._reload_plan()

    def _reload_plan(self) -> None:
        path_str = self._plan_path.text().strip()
        if not path_str:
            return
        try:
            from app.models.parser import parse_workout_file

            raw = json.loads(Path(path_str).read_bytes())
            self._plans = parse_workout_file(raw)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._status.setText(f"[ERROR] {exc}")
            self._plans = {}
            self._workout_combo.clear()
            return

        self._workout_combo.clear()
        for key in self._plans:
            self._workout_combo.addItem(key)

        last_key = self._config.last_workout_key
        idx = self._workout_combo.findText(last_key)
        if idx >= 0:
            self._workout_combo.setCurrentIndex(idx)

        self._status.setText(
            f"Loaded {len(self._plans)} workout(s) from {Path(path_str).name}"
        )
        self._save_config()

    def _refresh_credential_combo(self) -> None:
        self._cred_combo.clear()
        for e in self._creds_tab.entries():
            label = f"{e.service} ({e.login})" if e.login else e.service
            self._cred_combo.addItem(label, e)
        last_svc = self._config.last_credential_service
        last_login = self._config.last_credential_login
        for i in range(self._cred_combo.count()):
            cred: CredentialEntry = self._cred_combo.itemData(i)
            if cred.service == last_svc and cred.login == last_login:
                self._cred_combo.setCurrentIndex(i)
                break

    def _save_config(self) -> None:
        cred: CredentialEntry | None = self._cred_combo.currentData()
        self._config.last_plan_path = self._plan_path.text().strip()
        self._config.last_workout_key = self._workout_combo.currentText()
        self._config.last_connector = self._connector_combo.currentText()
        self._config.last_credential_service = cred.service if cred else ""
        self._config.last_credential_login = cred.login if cred else ""
        self._store.save_gui_config(self._config)

    @staticmethod
    def _keepass_paths_needed(cred: CredentialEntry | None) -> list[str]:
        if cred is not None and cred.source == "keepass" and cred.keepass_path:
            return [cred.keepass_path]
        return []

    def _prompt_keepass_passwords(
        self, paths: list[str]
    ) -> tuple[bool, dict[str, str]]:
        passwords: dict[str, str] = {}
        for path in paths:
            pw, ok = QInputDialog.getText(
                self,
                "KeePass master password",
                f"Master password for {path}:",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return False, {}
            passwords[path] = pw
        return True, passwords

    def _run_upload(self) -> None:
        self._refresh_credential_combo()
        plan_path = self._plan_path.text().strip()
        if not plan_path:
            QMessageBox.warning(self, "Missing plan", "Select a plan file first.")
            return
        if not self._plans:
            QMessageBox.warning(
                self, "No workouts", "No workouts loaded. Reload the plan file."
            )
            return

        workout_key = self._workout_combo.currentText() or None
        connector_name = self._connector_combo.currentText()
        cred: CredentialEntry | None = self._cred_combo.currentData()
        if cred is None:
            QMessageBox.warning(
                self,
                "No credential",
                "Add a credential in the Credentials tab first.",
            )
            return

        kp_paths = self._keepass_paths_needed(cred)
        proceed, kp_passwords = self._prompt_keepass_passwords(kp_paths)
        if not proceed:
            return

        self._log.clear()
        self._status.setText("Uploading...")
        self._upload_btn.setEnabled(False)
        self._save_config()

        self._worker = UploadWorker(
            plan_path=plan_path,
            workout_key=workout_key,
            connector_name=connector_name,
            credential_entries=self._creds_tab.entries(),
            keepass_passwords=kp_passwords,
            credential_service=cred.service,
            credential_login=cred.login,
            cache_dir=self._store.cache_dir,
        )
        self._worker.log_line.connect(self._on_log_line)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_log_line(self, line: str) -> None:
        self._log.append(line)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _on_finished(self, rc: int) -> None:
        self._upload_btn.setEnabled(True)
        self._status.setText("Done." if rc == 0 else "Upload failed.")
        self._worker = None


# ---------------------------------------------------------------------------
# Application icon
# ---------------------------------------------------------------------------


def make_app_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    return QIcon(pixmap)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self, store: ConfigStore) -> None:
        super().__init__()
        self.setWindowTitle("Training Plan Generator")
        self.resize(800, 600)

        tabs = QTabWidget()
        self._creds_tab = CredentialsTab(store)
        self._upload_tab = UploadTab(store, self._creds_tab)

        tabs.addTab(self._upload_tab, "Upload")
        tabs.addTab(self._creds_tab, "Credentials")
        tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(tabs)

        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(quit_action)

    def _on_tab_changed(self, index: int) -> None:
        if index == 0:
            self._upload_tab._refresh_credential_combo()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = QApplication(sys.argv)
    store = ConfigStore()
    window = MainWindow(store)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
