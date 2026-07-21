"""PySide6 GUI for training-plan-generator."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
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
    UploadTarget,
)

if TYPE_CHECKING:
    from app.adapters.base import PayloadAdapter
    from app.cache import WorkoutCache
    from app.connectors.base import WorkoutConnector
    from app.credentials.base import CredentialProvider, Credentials
    from app.models.workout import WorkoutPlan
    from app.run_log import RunLogger

_KNOWN_CREDENTIAL_URLS = ("https://connect.garmin.com",)


@dataclass
class ResolvedTarget:
    """An upload target whose credential reference has been resolved."""

    connector: str
    credential: CredentialEntry


# ---------------------------------------------------------------------------
# UploadWorker - runs the upload pipeline in a background QThread
# ---------------------------------------------------------------------------


class UploadWorker(QThread):
    log_line = Signal(str)
    finished = Signal(int)  # exit code: 0 = success, 1 = at least one failure

    def __init__(
        self,
        plan_path: str,
        targets: list[ResolvedTarget],
        keepass_passwords: dict[str, str],
        cache_dir: Path,
    ) -> None:
        super().__init__()
        self._plan_path = plan_path
        self._targets = targets
        self._keepass_passwords = keepass_passwords
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
        from app.cache import WorkoutCache
        from app.run_log import RunLogger

        log = RunLogger(self._cache_dir)
        cache = WorkoutCache(self._cache_dir)

        if not self._targets:
            self.log_line.emit("[ERROR] No upload targets configured.")
            log.error("no upload targets")
            return 1

        plans = self._load_plans(log)
        if plans is None:
            return 1

        # One source snapshot per run - it covers every workout in the file.
        source_path = cache.save_source_plan(
            Path(self._plan_path).stem, self._source_bytes or b""
        )
        log.info(f"source cached: {source_path}")

        failures = 0
        for target in self._targets:
            failures += self._upload_to_target(target, plans, cache, log)

        total = len(self._targets) * len(plans)
        self.log_line.emit(f"Finished: {total - failures}/{total} upload(s) succeeded.")
        self.log_line.emit(f"Log: {self._cache_dir / 'training_plan_generator.log'}")
        return 1 if failures else 0

    def _load_plans(self, log: RunLogger) -> list[WorkoutPlan] | None:
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

        self.log_line.emit(f"Loaded {len(plans)} workout(s).")
        log.info(f"plan loaded: {len(plans)} workout(s)")
        return plans

    def _upload_to_target(
        self,
        target: ResolvedTarget,
        plans: list[WorkoutPlan],
        cache: WorkoutCache,
        log: RunLogger,
    ) -> int:
        """Upload every plan to one target. Returns the number of failures."""
        import logging

        from app.connectors.registry import get_adapter, get_connector

        self.log_line.emit(f"--- {target.connector} / {target.credential.service} ---")

        creds = self._get_creds(target, log)
        if creds is None:
            return len(plans)

        self.log_line.emit(f"Logging in to {target.connector} ({creds.login})...")
        connector = get_connector(target.connector)
        garmin_logger = logging.getLogger("garminconnect.client")
        orig_level = garmin_logger.level
        garmin_logger.setLevel(logging.ERROR)
        try:
            connector.login(creds)
        except Exception as exc:
            self.log_line.emit(f"[ERROR] Login: {exc}")
            log.error(f"login error ({target.connector}): {exc}")
            return len(plans)
        finally:
            garmin_logger.setLevel(orig_level)

        log.info(f"login success: {target.connector}")
        adapter = get_adapter(target.connector)

        failures = 0
        for plan in plans:
            if not self._upload_plan(
                plan, adapter, connector, cache, target.connector, log
            ):
                failures += 1
        return failures

    def _upload_plan(
        self,
        plan: WorkoutPlan,
        adapter: PayloadAdapter,
        connector: WorkoutConnector,
        cache: WorkoutCache,
        connector_name: str,
        log: RunLogger,
    ) -> bool:
        adapt_result = adapter.to_payload(plan)
        for w in adapt_result.warnings:
            self.log_line.emit(f"[WARNING] {w}")
            log.warning(w)

        self.log_line.emit(f'Uploading "{plan.name}"...')
        try:
            workout_id = connector.upload(adapt_result.payload)
        except Exception as exc:
            self.log_line.emit(f"[ERROR] Upload {plan.name!r}: {exc}")
            log.error(f"upload error {plan.name!r}: {exc}")
            return False

        log.info(f"upload success: name={plan.name!r} id={workout_id}")
        payload_path = cache.save_connector_payload(
            plan.name, connector_name, adapt_result.payload
        )
        self.log_line.emit(f"  done (id={workout_id}), cached: {payload_path}")
        return True

    def _get_creds(self, target: ResolvedTarget, log: RunLogger) -> Credentials | None:
        from app.credentials.base import CredentialRequest, Credentials

        entry = target.credential
        self.log_line.emit("Reading credentials...")
        try:
            if entry.source == "keepass":
                provider = _keepass_provider(
                    entry.keepass_path, self._keepass_passwords, self._kp_providers
                )
                # The provider matches request.url as a *substring* of the
                # KeePass entry URL, so pass the connector name here exactly
                # like the CLI does. Passing the full stored URL would reject
                # entries whose URL is shorter (e.g. "connect.garmin.com").
                request = CredentialRequest(
                    service=entry.service,
                    url=target.connector,
                    login=entry.login or None,
                )
                return provider.get(request)
            return Credentials(login=entry.login, password=entry.password)
        except Exception as exc:
            self.log_line.emit(f"[ERROR] Credentials: {exc}")
            log.error(f"credentials error: {exc}")
            return None


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


def _find_credential(
    entries: list[CredentialEntry], service: str, login: str
) -> CredentialEntry | None:
    """Resolve a target's (service, login) reference to a stored credential."""
    for entry in entries:
        if entry.service == service and entry.login == login:
            return entry
    return None


def _keepass_paths(credentials: list[CredentialEntry]) -> list[str]:
    """Distinct .kdbx paths across credentials, in first-seen order.

    Deduplicating here is what keeps the GUI from asking for the same master
    password twice when several targets read from one KeePass database.
    """
    paths: list[str] = []
    for cred in credentials:
        if cred.source == "keepass" and cred.keepass_path:
            if cred.keepass_path not in paths:
                paths.append(cred.keepass_path)
    return paths


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
# TargetDialog
# ---------------------------------------------------------------------------


class TargetDialog(QDialog):
    """Pick a connector and one of the stored credentials for it."""

    def __init__(
        self,
        credentials: list[CredentialEntry],
        target: UploadTarget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Target" if target is None else "Edit Target")
        self.setMinimumWidth(400)

        form = QFormLayout(self)

        self._connector = QComboBox()
        self._connector.addItems(list(CONNECTOR_TYPES))
        if target is not None:
            idx = self._connector.findText(target.connector)
            if idx >= 0:
                self._connector.setCurrentIndex(idx)
        form.addRow("Connector:", self._connector)

        self._credential = QComboBox()
        for cred in credentials:
            label = f"{cred.service} ({cred.login})" if cred.login else cred.service
            self._credential.addItem(label, cred)
        if target is not None:
            for i in range(self._credential.count()):
                cred = self._credential.itemData(i)
                if (
                    cred.service == target.credential_service
                    and cred.login == target.credential_login
                ):
                    self._credential.setCurrentIndex(i)
                    break
        form.addRow("Credential:", self._credential)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setEnabled(self._credential.count() > 0)

    def result_target(self) -> UploadTarget:
        cred: CredentialEntry | None = self._credential.currentData()
        return UploadTarget(
            connector=self._connector.currentText(),
            credential_service=cred.service if cred else "",
            credential_login=cred.login if cred else "",
        )


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
        self._targets: list[UploadTarget] = store.load_targets()
        self._worker: UploadWorker | None = None

        root = QVBoxLayout(self)

        # Plan file group
        plan_box = QGroupBox("Plan file")
        plan_form = QFormLayout(plan_box)
        plan_row = QHBoxLayout()
        self._plan_path = QLineEdit(self._config.last_plan_path)
        self._plan_path.setPlaceholderText("Path to workout JSON file")
        self._plan_browse = QPushButton("Browse...")
        plan_row.addWidget(self._plan_path)
        plan_row.addWidget(self._plan_browse)
        plan_form.addRow("File:", plan_row)
        root.addWidget(plan_box)

        # Targets group - every workout in the file goes to every target here
        targets_box = QGroupBox("Upload targets")
        targets_layout = QVBoxLayout(targets_box)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Connector", "Credential"])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        targets_layout.addWidget(self._table)

        t_btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add")
        self._edit_btn = QPushButton("Edit")
        self._delete_btn = QPushButton("Delete")
        for btn in (self._add_btn, self._edit_btn, self._delete_btn):
            t_btn_row.addWidget(btn)
        t_btn_row.addStretch()
        targets_layout.addLayout(t_btn_row)
        root.addWidget(targets_box)

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
        self._plan_path.editingFinished.connect(self._save_config)
        self._add_btn.clicked.connect(self._add_target)
        self._edit_btn.clicked.connect(self._edit_target)
        self._delete_btn.clicked.connect(self._delete_target)
        self._upload_btn.clicked.connect(self._run_upload)

        self._refresh_table()

    # ------------------------------------------------------------------
    # Plan file
    # ------------------------------------------------------------------

    def _browse_plan(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Select workout plan", "", "JSON files (*.json);;All files (*)"
        )
        if path_str:
            self._plan_path.setText(path_str)
            self._save_config()

    def _save_config(self) -> None:
        self._config.last_plan_path = self._plan_path.text().strip()
        self._store.save_gui_config(self._config)

    # ------------------------------------------------------------------
    # Targets table
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        self._table.setRowCount(0)
        entries = self._creds_tab.entries()
        for target in self._targets:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(target.connector))
            cred = _find_credential(
                entries, target.credential_service, target.credential_login
            )
            label = (
                f"{target.credential_service} ({target.credential_login})"
                if target.credential_login
                else target.credential_service
            )
            if cred is None:
                label += "  [missing]"
            self._table.setItem(row, 1, QTableWidgetItem(label))

    def _add_target(self) -> None:
        entries = self._creds_tab.entries()
        if not entries:
            QMessageBox.warning(
                self,
                "No credentials",
                "Add a credential in the Credentials tab first.",
            )
            return
        dlg = TargetDialog(entries, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._targets.append(dlg.result_target())
            self._store.save_targets(self._targets)
            self._refresh_table()

    def _edit_target(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        entries = self._creds_tab.entries()
        if not entries:
            return
        dlg = TargetDialog(entries, target=self._targets[row], parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._targets[row] = dlg.result_target()
        self._store.save_targets(self._targets)
        self._refresh_table()

    def _delete_target(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        self._targets.pop(row)
        self._store.save_targets(self._targets)
        self._refresh_table()

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def _resolve_targets(self) -> tuple[list[ResolvedTarget], list[str]]:
        """Match every target's credential reference against stored credentials."""
        entries = self._creds_tab.entries()
        resolved: list[ResolvedTarget] = []
        missing: list[str] = []
        for target in self._targets:
            cred = _find_credential(
                entries, target.credential_service, target.credential_login
            )
            if cred is None:
                missing.append(f"{target.connector} / {target.credential_service}")
            else:
                resolved.append(ResolvedTarget(target.connector, cred))
        return resolved, missing

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
        plan_path = self._plan_path.text().strip()
        if not plan_path:
            QMessageBox.warning(self, "Missing plan", "Select a plan file first.")
            return
        if not self._targets:
            QMessageBox.warning(
                self, "No targets", "Add at least one upload target first."
            )
            return

        resolved, missing = self._resolve_targets()
        if missing:
            QMessageBox.warning(
                self,
                "Missing credentials",
                "These targets reference credentials that no longer exist:\n"
                + "\n".join(missing),
            )
            return

        kp_paths = _keepass_paths([t.credential for t in resolved])
        proceed, kp_passwords = self._prompt_keepass_passwords(kp_paths)
        if not proceed:
            return

        self._log.clear()
        self._status.setText("Uploading...")
        self._upload_btn.setEnabled(False)
        self._save_config()

        self._worker = UploadWorker(
            plan_path=plan_path,
            targets=resolved,
            keepass_passwords=kp_passwords,
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
        self.resize(800, 640)

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
        # Credentials may have been added or removed - re-check target labels.
        if index == 0:
            self._upload_tab._refresh_table()


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
