from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .about import about_details
from .dashboard import DashboardPage
from .database import encrypt_plaintext_database
from .domain import ItemControlError
from .repository import DEVICE_MODULE_VERSION, DEVICE_STATUSES, SQLiteRepository
from .service import DEVICE_IMPORT_COLUMNS, InventoryService
from .settings import add_recent_database, load_recent_databases


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        details = about_details()

        title = QLabel(details["name"])
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        self.version_label = QLabel(f"Versao {details['version']}")
        self.developer_label = QLabel(f"Desenvolvido por {details['developer']}")

        self.github_link = self._link_label(
            "Perfil no GitHub", details["developer_url"]
        )
        self.repository_link = self._link_label(
            "Repositorio do projeto", details["repository_url"]
        )
        self.releases_link = self._link_label(
            "Versoes e downloads", details["releases_url"]
        )

        links = QFormLayout()
        links.addRow("Desenvolvedor", self.github_link)
        links.addRow("Codigo-fonte", self.repository_link)
        links.addRow("Downloads", self.releases_link)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.version_label)
        layout.addWidget(self.developer_label)
        layout.addSpacing(16)
        layout.addLayout(links)
        layout.addStretch()

    @staticmethod
    def _link_label(text: str, url: str) -> QLabel:
        label = QLabel(f'<a href="{url}">{text}</a>')
        label.setToolTip(url)
        label.linkActivated.connect(
            lambda selected_url: QDesktopServices.openUrl(QUrl(selected_url))
        )
        return label


class NameEditDialog(QDialog):
    def __init__(
        self,
        title: str,
        label: str,
        value: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.name_input = QLineEdit(value)

        form = QFormLayout()
        form.addRow(label, self.name_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def name(self) -> str:
        return self.name_input.text().strip()

    def accept(self) -> None:
        if not self.name():
            QMessageBox.warning(self, "ItemControl", "Informe um nome.")
            return
        super().accept()


class LocationQuickCreateDialog(QDialog):
    def __init__(
        self,
        service: InventoryService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.created_location_id: int | None = None
        self.setWindowTitle("Novo local")

        self.country_combo = QComboBox()
        for country in self.service.countries():
            self.country_combo.addItem(country["name"], country["id"])
        self.location_input = QLineEdit()

        form = QFormLayout()
        form.addRow("Pais", self.country_combo)
        form.addRow("Local", self.location_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self) -> None:
        country_id = self.country_combo.currentData()
        if country_id is None:
            QMessageBox.warning(self, "ItemControl", "Selecione um pais.")
            return
        try:
            self.created_location_id = self.service.create_location(
                int(country_id),
                self.location_input.text(),
            )
        except ItemControlError as exc:
            QMessageBox.warning(self, "ItemControl", str(exc))
            return
        super().accept()


class DeviceFormDialog(QDialog):
    def __init__(
        self,
        service: InventoryService,
        device: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.device = device
        self.saved = False
        self.setWindowTitle("Editar Device" if device else "Novo Device")
        self.resize(560, 360)

        self.serial_input = QLineEdit(device["serial"] if device else "")
        self.name_input = QLineEdit(device["name"] if device else "")
        self.type_combo = QComboBox()
        self.status_combo = QComboBox()
        self.status_combo.addItems(DEVICE_STATUSES)
        self.user_combo = QComboBox()
        self.location_combo = QComboBox()
        self.note_input = QLineEdit(device["note"] or "" if device else "")

        self.type_add_button = QPushButton("+")
        self.type_add_button.setToolTip("Cadastrar novo tipo")
        self.type_add_button.clicked.connect(self.create_type)
        self.user_add_button = QPushButton("+")
        self.user_add_button.setToolTip("Cadastrar novo usuario")
        self.user_add_button.clicked.connect(self.create_user)
        self.location_add_button = QPushButton("+")
        self.location_add_button.setToolTip("Cadastrar novo local")
        self.location_add_button.clicked.connect(self.create_location)

        type_row = QHBoxLayout()
        type_row.addWidget(self.type_combo, 1)
        type_row.addWidget(self.type_add_button)
        user_row = QHBoxLayout()
        user_row.addWidget(self.user_combo, 1)
        user_row.addWidget(self.user_add_button)
        location_row = QHBoxLayout()
        location_row.addWidget(self.location_combo, 1)
        location_row.addWidget(self.location_add_button)

        form = QFormLayout()
        form.addRow("Serial", self.serial_input)
        form.addRow("Nome", self.name_input)
        form.addRow("Tipo", type_row)
        form.addRow("Status", self.status_combo)
        form.addRow("Usuario", user_row)
        form.addRow("Local", location_row)
        form.addRow("Observacao", self.note_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.status_combo.currentTextChanged.connect(self._status_changed)
        self.load_options()
        if device is not None:
            self._select_current_values(device)
        self._status_changed(self.status_combo.currentText())

    @staticmethod
    def _selected_id(combo: QComboBox) -> int | None:
        data = combo.currentData()
        return None if data is None else int(data)

    @staticmethod
    def _load_combo(combo: QComboBox, rows, label_builder, allow_blank: bool = False) -> None:
        current = combo.currentData()
        combo.clear()
        if allow_blank:
            combo.addItem("Sem usuario", None)
        for row in rows:
            combo.addItem(label_builder(row), row["id"])
        if current is not None:
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)

    def _option_rows_with_current(self, active_rows, all_rows, current_id: int | None):
        rows = list(active_rows)
        if current_id is not None and all(row["id"] != current_id for row in rows):
            current_row = next((row for row in all_rows if row["id"] == current_id), None)
            if current_row is not None:
                rows.append(current_row)
        return rows

    def load_options(self) -> None:
        current_type_id = int(self.device["device_type_id"]) if self.device else None
        current_user_id = self.device["user_id"] if self.device else None
        active_types = self.service.active_device_types()
        active_users = self.service.active_device_users()
        all_types = self.service.device_types()
        all_users = self.service.device_users()
        type_rows = self._option_rows_with_current(active_types, all_types, current_type_id)
        user_rows = self._option_rows_with_current(active_users, all_users, current_user_id)
        self._load_combo(
            self.type_combo,
            type_rows,
            lambda row: row["name"] if row.get("is_active", 1) else f"{row['name']} (inativo)",
        )
        self._load_combo(
            self.user_combo,
            user_rows,
            lambda row: row["name"] if row.get("is_active", 1) else f"{row['name']} (inativo)",
            True,
        )
        self._load_combo(
            self.location_combo,
            self.service.locations(),
            lambda row: f"{row['country_name']} - {row['name']}",
        )

    def _select_current_values(self, device: dict) -> None:
        for combo, key in (
            (self.type_combo, "device_type_id"),
            (self.user_combo, "user_id"),
            (self.location_combo, "location_id"),
        ):
            value = device[key]
            if value is not None:
                index = combo.findData(value)
                if index >= 0:
                    combo.setCurrentIndex(index)
        status_index = self.status_combo.findText(device["status"])
        if status_index >= 0:
            self.status_combo.setCurrentIndex(status_index)

    def _status_changed(self, status: str) -> None:
        requires_user = status == "Em uso"
        self.user_combo.setEnabled(requires_user)
        self.user_add_button.setEnabled(requires_user)
        if not requires_user:
            self.user_combo.setCurrentIndex(0)

    def create_type(self) -> None:
        dialog = NameEditDialog("Novo tipo", "Tipo", parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            type_id = self.service.create_device_type(dialog.name())
        except ItemControlError as exc:
            QMessageBox.warning(self, "ItemControl", str(exc))
            return
        self.load_options()
        index = self.type_combo.findData(type_id)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)

    def create_user(self) -> None:
        dialog = NameEditDialog("Novo usuario", "Usuario", parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            user_id = self.service.create_device_user(dialog.name())
        except ItemControlError as exc:
            QMessageBox.warning(self, "ItemControl", str(exc))
            return
        self.load_options()
        index = self.user_combo.findData(user_id)
        if index >= 0:
            self.user_combo.setCurrentIndex(index)

    def create_location(self) -> None:
        dialog = LocationQuickCreateDialog(self.service, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.load_options()
        if dialog.created_location_id is not None:
            index = self.location_combo.findData(dialog.created_location_id)
            if index >= 0:
                self.location_combo.setCurrentIndex(index)

    def save(self) -> None:
        device_type_id = self._selected_id(self.type_combo)
        location_id = self._selected_id(self.location_combo)
        user_id = self._selected_id(self.user_combo)
        if device_type_id is None or location_id is None:
            QMessageBox.warning(self, "ItemControl", "Selecione tipo e local.")
            return
        try:
            if self.device is None:
                self.service.create_device(
                    self.serial_input.text(),
                    self.name_input.text(),
                    device_type_id,
                    self.status_combo.currentText(),
                    location_id,
                    user_id,
                    self.note_input.text(),
                )
            else:
                self.service.update_device_details(
                    int(self.device["id"]),
                    self.serial_input.text(),
                    self.name_input.text(),
                    device_type_id,
                    self.status_combo.currentText(),
                    location_id,
                    user_id,
                    self.note_input.text(),
                )
        except ItemControlError as exc:
            QMessageBox.warning(self, "ItemControl", str(exc))
            return
        self.saved = True
        self.accept()


class DeviceModulePage(QWidget):
    def __init__(
        self,
        service: InventoryService,
        import_devices_callback=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.import_devices_callback = import_devices_callback

        self.users_table = QTableWidget()
        self.types_table = QTableWidget()
        self.devices_table = QTableWidget()
        self.transfers_list = QListWidget()

        self.device_new_button = QPushButton("Novo")
        self.device_new_button.clicked.connect(self.open_new_device)
        self.device_edit_button = QPushButton("Editar")
        self.device_edit_button.clicked.connect(self.open_selected_device)
        self.device_toggle_button = QPushButton("Desativar/Reativar")
        self.device_toggle_button.clicked.connect(self.toggle_selected_device)
        self.device_refresh_button = QPushButton("Atualizar")
        self.device_refresh_button.clicked.connect(self.refresh)
        self.device_import_button = QPushButton("Importar Devices CSV")
        self.device_import_button.clicked.connect(self._open_import)

        self.user_new_button = QPushButton("Novo")
        self.user_new_button.clicked.connect(self.create_user)
        self.user_edit_button = QPushButton("Editar")
        self.user_edit_button.clicked.connect(self.edit_user)
        self.user_toggle_button = QPushButton("Inativar/Reativar")
        self.user_toggle_button.clicked.connect(self.toggle_user)

        self.type_new_button = QPushButton("Novo")
        self.type_new_button.clicked.connect(self.create_type)
        self.type_edit_button = QPushButton("Editar")
        self.type_edit_button.clicked.connect(self.edit_type)
        self.type_toggle_button = QPushButton("Inativar/Reativar")
        self.type_toggle_button.clicked.connect(self.toggle_type)

        self.transfer_device_combo = QComboBox()
        self.transfer_status_combo = QComboBox()
        self.transfer_status_combo.addItem("Manter atual", None)
        for status in DEVICE_STATUSES:
            self.transfer_status_combo.addItem(status, status)
        self.transfer_user_combo = QComboBox()
        self.transfer_location_combo = QComboBox()
        self.transfer_note_input = QLineEdit()
        self.transfer_button = QPushButton("Transferir dispositivo")
        self.transfer_button.clicked.connect(self.transfer_device)

        layout = QVBoxLayout(self)
        self.device_tabs = QTabWidget()
        layout.addWidget(self.device_tabs)
        self._build_devices_table()
        self._build_records_table(self.users_table)
        self._build_records_table(self.types_table)

        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        list_actions = QHBoxLayout()
        list_actions.addWidget(self.device_new_button)
        list_actions.addWidget(self.device_edit_button)
        list_actions.addWidget(self.device_toggle_button)
        list_actions.addWidget(self.device_refresh_button)
        if import_devices_callback is not None:
            list_actions.addWidget(self.device_import_button)
        list_actions.addStretch()
        list_layout.addLayout(list_actions)
        list_layout.addWidget(self.devices_table, 1)

        transfers_page = QWidget()
        transfer_page_layout = QVBoxLayout(transfers_page)
        transfer_box = QGroupBox("Transferencia")
        transfer_layout = QVBoxLayout(transfer_box)
        transfer_form = QFormLayout()
        transfer_form.addRow("Dispositivo", self.transfer_device_combo)
        transfer_form.addRow("Novo status", self.transfer_status_combo)
        transfer_form.addRow("Novo usuario", self.transfer_user_combo)
        transfer_form.addRow("Novo local", self.transfer_location_combo)
        transfer_form.addRow("Observacao", self.transfer_note_input)
        transfer_layout.addLayout(transfer_form)
        transfer_layout.addWidget(self.transfer_button)
        transfer_page_layout.addWidget(transfer_box)
        transfer_page_layout.addWidget(self.transfers_list, 1)

        records_page = QWidget()
        records_layout = QGridLayout(records_page)
        users_box = QGroupBox("Usuarios")
        users_layout = QVBoxLayout(users_box)
        users_actions = QHBoxLayout()
        users_actions.addWidget(self.user_new_button)
        users_actions.addWidget(self.user_edit_button)
        users_actions.addWidget(self.user_toggle_button)
        users_actions.addStretch()
        users_layout.addLayout(users_actions)
        users_layout.addWidget(self.users_table)

        types_box = QGroupBox("Tipos")
        types_layout = QVBoxLayout(types_box)
        types_actions = QHBoxLayout()
        types_actions.addWidget(self.type_new_button)
        types_actions.addWidget(self.type_edit_button)
        types_actions.addWidget(self.type_toggle_button)
        types_actions.addStretch()
        types_layout.addLayout(types_actions)
        types_layout.addWidget(self.types_table)

        records_layout.addWidget(users_box, 0, 0)
        records_layout.addWidget(types_box, 0, 1)

        self.device_tabs.addTab(list_page, "Lista")
        self.device_tabs.addTab(transfers_page, "Transferencias")
        self.device_tabs.addTab(records_page, "Cadastros")

        self.refresh()

    def set_service(self, service: InventoryService) -> None:
        self.service = service

    def _build_devices_table(self) -> None:
        self.devices_table.setColumnCount(7)
        self.devices_table.setHorizontalHeaderLabels(
            ["Serial", "Nome", "Tipo", "Status", "Usuario", "Pais", "Local"]
        )
        self.devices_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.devices_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.devices_table.setSortingEnabled(True)
        self.devices_table.itemDoubleClicked.connect(
            lambda _item: self.open_selected_device()
        )
        header = self.devices_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.devices_table.setMinimumHeight(360)

    def _build_records_table(self, table: QTableWidget) -> None:
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Nome", "Status"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

    @staticmethod
    def _selected_id(combo: QComboBox) -> int | None:
        data = combo.currentData()
        return None if data is None else int(data)

    def _notify(self, message: str, error: bool = False) -> None:
        window = self.window()
        handler_name = "show_error" if error else "show_info"
        handler = getattr(window, handler_name, None)
        if callable(handler):
            handler(message)

    def _open_import(self) -> None:
        if callable(self.import_devices_callback):
            self.import_devices_callback()

    def _load_combo(self, combo: QComboBox, rows, label_builder, allow_blank: bool = False) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        if allow_blank:
            combo.addItem("Sem usuario", None)
        for row in rows:
            combo.addItem(label_builder(row), row["id"])
        if current is not None:
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def refresh(self) -> None:
        users = self.service.device_users()
        active_users = self.service.active_device_users()
        types = self.service.device_types()
        devices = self.service.devices()
        transfers = self.service.device_transfers()
        locations = self.service.locations()

        self._fill_records_table(self.users_table, users)
        self._fill_records_table(self.types_table, types)
        self._fill_devices_table(devices)

        self.transfers_list.clear()
        for row in transfers:
            to_user = row["to_user_name"] or "-"
            from_user = row["from_user_name"] or "-"
            self.transfers_list.addItem(
                f"#{row['id']} {row['device_serial']} - {row['device_name']} | {row['device_type_name']} | {from_user} -> {to_user} | {row['from_location_name']} -> {row['to_location_name']} | {row['from_status']} -> {row['to_status']}"
            )

        self._load_combo(
            self.transfer_device_combo,
            devices,
            lambda r: f"{r['serial']} - {r['name']} ({r['device_type_name']})",
        )
        self._load_combo(self.transfer_user_combo, active_users, lambda r: r["name"], True)
        self._load_combo(
            self.transfer_location_combo,
            locations,
            lambda r: f"{r['country_name']} - {r['name']}",
        )

    def _fill_devices_table(self, devices) -> None:
        self.devices_table.setSortingEnabled(False)
        self.devices_table.setRowCount(len(devices))
        for row_index, row in enumerate(devices):
            values = (
                row["serial"],
                row["name"],
                row["device_type_name"],
                row["status"],
                row["user_name"] or "-",
                row["country_name"],
                row["location_name"],
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row["id"])
                self.devices_table.setItem(row_index, column_index, item)
        self.devices_table.setSortingEnabled(True)

    def _fill_records_table(self, table: QTableWidget, rows) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            name_item = QTableWidgetItem(str(row["name"]))
            name_item.setData(Qt.UserRole, row["id"])
            name_item.setData(Qt.UserRole + 1, int(row.get("is_active", 1)))
            status_item = QTableWidgetItem(
                "Ativo" if int(row.get("is_active", 1)) else "Inativo"
            )
            status_item.setData(Qt.UserRole, row["id"])
            status_item.setData(Qt.UserRole + 1, int(row.get("is_active", 1)))
            table.setItem(row_index, 0, name_item)
            table.setItem(row_index, 1, status_item)
        table.setSortingEnabled(True)

    def _selected_table_id(self, table: QTableWidget) -> int | None:
        selected = table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return None if data is None else int(data)

    def _selected_table_active(self, table: QTableWidget) -> bool | None:
        selected = table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.UserRole + 1)
        return None if data is None else bool(int(data))

    def _device_by_id(self, device_id: int):
        return next(
            (row for row in self.service.devices() if int(row["id"]) == device_id),
            None,
        )

    def create_user(self) -> None:
        dialog = NameEditDialog("Novo usuario", "Usuario", parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.create_device_user(dialog.name())
        except ItemControlError as exc:
            self._notify(str(exc), error=True)
            return
        self._refresh_window()
        self._notify("Usuario cadastrado com sucesso.")

    def create_type(self) -> None:
        dialog = NameEditDialog("Novo tipo", "Tipo", parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.create_device_type(dialog.name())
        except ItemControlError as exc:
            self._notify(str(exc), error=True)
            return
        self._refresh_window()
        self._notify("Tipo cadastrado com sucesso.")

    def _refresh_window(self) -> None:
        window = self.window()
        refresh_all = getattr(window, "refresh_all", None)
        if callable(refresh_all):
            refresh_all()
        else:
            self.refresh()

    def open_new_device(self) -> None:
        dialog = DeviceFormDialog(self.service, parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.saved:
            return
        self._refresh_window()
        self._notify("Dispositivo cadastrado com sucesso.")

    def open_selected_device(self) -> None:
        device_id = self._selected_table_id(self.devices_table)
        if device_id is None:
            self._notify("Selecione um dispositivo.", error=True)
            return
        device = self._device_by_id(device_id)
        if device is None:
            self._notify("Dispositivo nao encontrado.", error=True)
            return
        dialog = DeviceFormDialog(self.service, device=device, parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.saved:
            return
        self._refresh_window()
        self._notify("Dispositivo atualizado com sucesso.")

    def toggle_selected_device(self) -> None:
        device_id = self._selected_table_id(self.devices_table)
        if device_id is None:
            self._notify("Selecione um dispositivo.", error=True)
            return
        device = self._device_by_id(device_id)
        if device is None:
            self._notify("Dispositivo nao encontrado.", error=True)
            return
        action = "reativar" if device["status"] == "Desativado" else "desativar"
        answer = QMessageBox.question(
            self,
            "ItemControl",
            f"Deseja {action} o device {device['serial']}?",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            new_status = self.service.toggle_device_deactivated(device_id)
        except ItemControlError as exc:
            self._notify(str(exc), error=True)
            return
        self._refresh_window()
        self._notify(f"Device atualizado para {new_status}.")

    def edit_user(self) -> None:
        user_id = self._selected_table_id(self.users_table)
        if user_id is None:
            self._notify("Selecione um usuario.", error=True)
            return
        user = next((row for row in self.service.device_users() if row["id"] == user_id), None)
        if user is None:
            self._notify("Usuario nao encontrado.", error=True)
            return
        dialog = NameEditDialog("Editar usuario", "Usuario", user["name"], self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_device_user_name(user_id, dialog.name())
        except ItemControlError as exc:
            self._notify(str(exc), error=True)
            return
        self._refresh_window()
        self._notify("Usuario atualizado com sucesso.")

    def edit_type(self) -> None:
        type_id = self._selected_table_id(self.types_table)
        if type_id is None:
            self._notify("Selecione um tipo.", error=True)
            return
        device_type = next((row for row in self.service.device_types() if row["id"] == type_id), None)
        if device_type is None:
            self._notify("Tipo nao encontrado.", error=True)
            return
        dialog = NameEditDialog("Editar tipo", "Tipo", device_type["name"], self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_device_type_name(type_id, dialog.name())
        except ItemControlError as exc:
            self._notify(str(exc), error=True)
            return
        self._refresh_window()
        self._notify("Tipo atualizado com sucesso.")

    def toggle_user(self) -> None:
        user_id = self._selected_table_id(self.users_table)
        is_active = self._selected_table_active(self.users_table)
        if user_id is None or is_active is None:
            self._notify("Selecione um usuario.", error=True)
            return
        action = "inativar" if is_active else "reativar"
        answer = QMessageBox.question(
            self,
            "ItemControl",
            f"Deseja {action} este usuario?",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.set_device_user_active(user_id, not is_active)
        except ItemControlError as exc:
            self._notify(str(exc), error=True)
            return
        self._refresh_window()
        self._notify("Usuario atualizado com sucesso.")

    def toggle_type(self) -> None:
        type_id = self._selected_table_id(self.types_table)
        is_active = self._selected_table_active(self.types_table)
        if type_id is None or is_active is None:
            self._notify("Selecione um tipo.", error=True)
            return
        action = "inativar" if is_active else "reativar"
        answer = QMessageBox.question(
            self,
            "ItemControl",
            f"Deseja {action} este tipo?",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.set_device_type_active(type_id, not is_active)
        except ItemControlError as exc:
            self._notify(str(exc), error=True)
            return
        self._refresh_window()
        self._notify("Tipo atualizado com sucesso.")

    def transfer_device(self) -> None:
        device_id = self._selected_id(self.transfer_device_combo)
        location_id = self._selected_id(self.transfer_location_combo)
        if device_id is None or location_id is None:
            self._notify("Selecione dispositivo e local.", error=True)
            return
        try:
            self.service.transfer_device(
                device_id,
                location_id,
                self._selected_id(self.transfer_user_combo),
                self.transfer_status_combo.currentData(),
                self.transfer_note_input.text(),
            )
        except ItemControlError as exc:
            self._notify(str(exc), error=True)
            return
        self.transfer_note_input.clear()
        self.refresh()
        self._notify("Dispositivo transferido com sucesso.")


class DeviceCsvImportDialog(QDialog):
    CSV_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")

    def __init__(
        self,
        service: InventoryService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.imported_count = 0
        self.setWindowTitle("Importar Devices CSV")
        self.resize(1080, 720)

        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        browse_button = QPushButton("Selecionar CSV")
        browse_button.clicked.connect(self.browse_csv)
        template_button = QPushButton("Salvar template")
        template_button.clicked.connect(self.save_template)

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(browse_button)
        path_row.addWidget(template_button)

        self.default_type_input = QLineEdit()
        self.default_status_combo = QComboBox()
        self.default_status_combo.addItem("", "")
        self.default_status_combo.addItems(DEVICE_STATUSES)
        self.default_user_input = QLineEdit()
        self.default_country_input = QLineEdit()
        self.default_location_input = QLineEdit()
        self.default_note_input = QLineEdit()

        defaults_form = QFormLayout()
        defaults_form.addRow("Tipo", self.default_type_input)
        defaults_form.addRow("Status", self.default_status_combo)
        defaults_form.addRow("Usuario", self.default_user_input)
        defaults_form.addRow("Pais", self.default_country_input)
        defaults_form.addRow("Local", self.default_location_input)
        defaults_form.addRow("Observacao", self.default_note_input)

        defaults_box = QGroupBox("Padroes para campos vazios")
        defaults_box.setLayout(defaults_form)

        self.table = QTableWidget(0, len(DEVICE_IMPORT_COLUMNS) + 1)
        self.table.setHorizontalHeaderLabels([*DEVICE_IMPORT_COLUMNS, "errors"])
        self.table.setMinimumHeight(320)
        self.table.setSortingEnabled(False)

        apply_defaults_button = QPushButton("Aplicar padroes")
        apply_defaults_button.clicked.connect(self.apply_defaults)
        validate_button = QPushButton("Validar")
        validate_button.clicked.connect(self.validate_rows)
        import_button = QPushButton("Importar linhas validas")
        import_button.clicked.connect(self.import_valid_rows)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.reject)

        actions = QHBoxLayout()
        actions.addWidget(apply_defaults_button)
        actions.addWidget(validate_button)
        actions.addWidget(import_button)
        actions.addStretch()
        actions.addWidget(close_button)

        self.summary_label = QLabel("Nenhum CSV carregado.")
        self.report_area = QTextEdit()
        self.report_area.setReadOnly(True)
        self.report_area.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Colunas esperadas: " + ", ".join(DEVICE_IMPORT_COLUMNS)))
        layout.addLayout(path_row)
        layout.addWidget(defaults_box)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.report_area)

    def browse_csv(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar CSV de Devices",
            "",
            "CSV files (*.csv);;All files (*)",
        )
        if filename:
            self.load_csv(filename)

    def save_template(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar template CSV",
            "devices-template.csv",
            "CSV files (*.csv);;All files (*)",
        )
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8-sig", newline="") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=DEVICE_IMPORT_COLUMNS,
                    delimiter=";",
                )
                writer.writeheader()
        except OSError as exc:
            QMessageBox.warning(self, "ItemControl", f"Nao foi possivel salvar: {exc}")
            return
        QMessageBox.information(self, "ItemControl", "Template CSV salvo com sucesso.")

    def load_csv(self, filename: str) -> None:
        try:
            read_result = self._read_device_csv(filename)
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            QMessageBox.warning(
                self,
                "ItemControl",
                (
                    "Nao foi possivel ler o CSV. Use um arquivo CSV UTF-8 ou "
                    f"Windows/Excel ANSI. Detalhes: {exc}"
                ),
            )
            return

        fieldnames = read_result["fieldnames"]
        missing = [column for column in DEVICE_IMPORT_COLUMNS if column not in fieldnames]
        if missing:
            QMessageBox.warning(
                self,
                "ItemControl",
                "CSV sem colunas obrigatorias: " + ", ".join(missing),
            )
            return

        rows = read_result["rows"]
        self.path_input.setText(filename)
        self._fill_table(rows)
        delimiter_name = "ponto e virgula" if read_result["delimiter"] == ";" else "virgula"
        self.summary_label.setText(
            (
                f"{len(rows)} linhas carregadas. "
                f"Encoding: {read_result['encoding']}; separador: {delimiter_name}."
            )
        )
        self.report_area.clear()
        if rows:
            self.validate_rows()

    @classmethod
    def _read_device_csv(cls, filename: str) -> dict:
        last_error: Exception | None = None
        for encoding in cls.CSV_ENCODINGS:
            try:
                with open(filename, "r", encoding=encoding, newline="") as csv_file:
                    content = csv_file.read()
            except UnicodeDecodeError as exc:
                last_error = exc
                continue

            delimiter = cls._detect_csv_delimiter(content)
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            rows = [
                {
                    column: (source_row.get(column) or "").strip()
                    for column in DEVICE_IMPORT_COLUMNS
                }
                for source_row in reader
            ]
            return {
                "rows": rows,
                "fieldnames": reader.fieldnames or [],
                "encoding": encoding,
                "delimiter": delimiter,
            }
        if last_error is not None:
            raise last_error
        raise UnicodeDecodeError("csv", b"", 0, 1, "could not decode file")

    @staticmethod
    def _detect_csv_delimiter(content: str) -> str:
        for line in content.splitlines():
            if line.strip():
                return ";" if line.count(";") >= line.count(",") else ","
        return ","

    def _fill_table(self, rows: list[dict[str, str]]) -> None:
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, column in enumerate(DEVICE_IMPORT_COLUMNS):
                self.table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(row.get(column, "")),
                )
            self._set_error_cell(row_index, "")

    def _set_error_cell(self, row_index: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row_index, len(DEVICE_IMPORT_COLUMNS), item)

    def _rows_from_table(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row_index in range(self.table.rowCount()):
            row = {}
            for column_index, column in enumerate(DEVICE_IMPORT_COLUMNS):
                item = self.table.item(row_index, column_index)
                row[column] = item.text().strip() if item is not None else ""
            rows.append(row)
        return rows

    def apply_defaults(self) -> None:
        defaults = {
            "device_type": self.default_type_input.text().strip(),
            "status": self.default_status_combo.currentText().strip(),
            "user": self.default_user_input.text().strip(),
            "country": self.default_country_input.text().strip(),
            "location": self.default_location_input.text().strip(),
            "note": self.default_note_input.text().strip(),
        }
        for row_index in range(self.table.rowCount()):
            for column, value in defaults.items():
                if not value:
                    continue
                column_index = DEVICE_IMPORT_COLUMNS.index(column)
                item = self.table.item(row_index, column_index)
                if item is None:
                    item = QTableWidgetItem("")
                    self.table.setItem(row_index, column_index, item)
                if not item.text().strip():
                    item.setText(value)
        self.validate_rows()

    def validate_rows(self) -> None:
        rows = self._rows_from_table()
        if not rows:
            self.summary_label.setText("Nenhuma linha para validar.")
            self.report_area.clear()
            return
        result = self.service.validate_device_import_rows(rows)
        self._apply_validation_result(result, imported=False)

    def import_valid_rows(self) -> None:
        rows = self._rows_from_table()
        if not rows:
            QMessageBox.warning(self, "ItemControl", "Nenhuma linha para importar.")
            return
        result = self.service.import_device_rows(rows)
        self.imported_count += int(result["imported"])
        self._apply_validation_result(result, imported=True)
        QMessageBox.information(
            self,
            "ItemControl",
            (
                f"Importacao concluida. Importados: {result['imported']}. "
                f"Invalidos/ignorados: {result['invalid']}."
            ),
        )

    def _apply_validation_result(self, result: dict, imported: bool) -> None:
        report_lines = []
        for row_result in result["rows"]:
            errors = row_result["errors"]
            error_text = "; ".join(errors)
            if row_result.get("imported"):
                error_text = "Importado."
            self._set_error_cell(int(row_result["row"]) - 1, error_text)
            if errors:
                csv_line = int(row_result["row"]) + 1
                report_lines.append(
                    f"Linha {csv_line}: " + "; ".join(errors)
                )

        action = "Importacao" if imported else "Validacao"
        self.summary_label.setText(
            (
                f"{action}: {result['total']} linhas, "
                f"{result['valid']} validas, {result['invalid']} invalidas, "
                f"{result['imported']} importadas."
            )
        )
        self.report_area.setPlainText("\n".join(report_lines))


class PasswordConfirmationDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Senha da base")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)

        form = QFormLayout()
        form.addRow("Senha", self.password_input)
        form.addRow("Confirmar senha", self.confirm_password_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def password(self) -> str:
        return self.password_input.text()

    def accept(self) -> None:
        if not self.password_input.text().strip():
            QMessageBox.warning(self, "ItemControl", "Informe uma senha.")
            return
        if self.password_input.text() != self.confirm_password_input.text():
            QMessageBox.warning(self, "ItemControl", "As senhas nao conferem.")
            return
        super().accept()


class DatabaseSelectionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Abrir base de dados")
        self.resize(560, 360)
        self.database_path: str | None = None
        self.database_password: str | None = None

        self.recent_list = QListWidget()
        for database_path in load_recent_databases():
            self.recent_list.addItem(database_path)
        self.recent_list.itemClicked.connect(
            lambda item: self.path_input.setText(item.text())
        )
        self.recent_list.itemDoubleClicked.connect(lambda item: self.open_existing())

        self.path_input = QLineEdit("itemcontrol.sqlite3")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)

        browse_button = QPushButton("Procurar")
        browse_button.clicked.connect(self.browse_existing)
        new_button = QPushButton("Nova base")
        new_button.clicked.connect(self.create_new)
        open_button = QPushButton("Abrir")
        open_button.clicked.connect(self.open_existing)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_input)
        path_row.addWidget(browse_button)

        form = QFormLayout()
        form.addRow("Arquivo", path_row)
        form.addRow("Senha", self.password_input)
        form.addRow("Confirmar senha", self.confirm_password_input)

        buttons = QHBoxLayout()
        buttons.addWidget(open_button)
        buttons.addWidget(new_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Bases recentes"))
        layout.addWidget(self.recent_list)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def browse_existing(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir base de dados",
            "",
            "SQLite databases (*.sqlite3 *.db);;All files (*)",
        )
        if filename:
            self.path_input.setText(filename)

    def create_new(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Criar base de dados",
            self.path_input.text() or "itemcontrol.sqlite3",
            "SQLite databases (*.sqlite3 *.db);;All files (*)",
        )
        if not filename:
            return
        if Path(filename).exists():
            QMessageBox.warning(self, "ItemControl", "O arquivo escolhido ja existe.")
            return
        if self.password_input.text() != self.confirm_password_input.text():
            QMessageBox.warning(self, "ItemControl", "As senhas nao conferem.")
            return
        try:
            repository = SQLiteRepository(filename, self.password_input.text() or None)
            repository.close()
        except ItemControlError as exc:
            QMessageBox.warning(self, "ItemControl", str(exc))
            return
        self._accept_database(filename, self.password_input.text() or None)

    def open_existing(self) -> None:
        filename = self.path_input.text().strip()
        if not filename:
            QMessageBox.warning(self, "ItemControl", "Escolha uma base de dados.")
            return
        if not Path(filename).exists():
            QMessageBox.warning(self, "ItemControl", "A base escolhida nao existe.")
            return
        try:
            repository = SQLiteRepository(filename, self.password_input.text() or None)
            repository.close()
        except ItemControlError as exc:
            QMessageBox.warning(self, "ItemControl", str(exc))
            return
        self._accept_database(filename, self.password_input.text() or None)

    def _accept_database(self, database_path: str, password: str | None) -> None:
        self.database_path = database_path
        self.database_password = password
        add_recent_database(database_path)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: InventoryService,
        database_path: str,
        database_password: str | None = None,
        device_module_enabled: bool | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.database_path = database_path
        self.database_password = database_password
        if device_module_enabled is None:
            device_module_enabled = self.service.repository.has_device_schema()
        self.device_module_enabled = device_module_enabled
        self.setWindowTitle(f"ItemControl - {database_path}")
        self.resize(1150, 780)

        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setMinimumHeight(110)

        self.tabs = QTabWidget()
        self.countries_list = QListWidget()
        self.locations_list = QListWidget()
        self.items_list = QListWidget()
        self.movements_list = QListWidget()
        self.stock_distribution_list = QListWidget()
        self.stock_table = QTableWidget()

        self.country_name_input = QLineEdit()
        self.country_create_button = QPushButton("Cadastrar pais")
        self.country_create_button.clicked.connect(self.create_country)

        self.location_country_combo = QComboBox()
        self.location_name_input = QLineEdit()
        self.location_create_button = QPushButton("Cadastrar local")
        self.location_create_button.clicked.connect(self.create_location)

        self.item_serial_input = QLineEdit()
        self.item_serial_input.setPlaceholderText("Opcional")
        self.item_name_input = QLineEdit()
        self.item_create_button = QPushButton("Cadastrar item")
        self.item_create_button.clicked.connect(self.create_item)

        self.movement_item_combo = QComboBox()
        self.movement_from_location_combo = QComboBox()
        self.movement_to_location_combo = QComboBox()
        self.movement_quantity_spin = QSpinBox()
        self.movement_quantity_spin.setMinimum(1)
        self.movement_quantity_spin.setMaximum(100000)
        self.movement_note_input = QLineEdit()

        self.add_button = QPushButton("Adicionar")
        self.remove_button = QPushButton("Retirar")
        self.transfer_button = QPushButton("Transferir")
        self.add_button.clicked.connect(self.add_item)
        self.remove_button.clicked.connect(self.remove_item)
        self.transfer_button.clicked.connect(self.transfer_item)

        self.balance_location_combo = QComboBox()
        self.balance_value_label = QLabel("0")
        self.balance_refresh_button = QPushButton("Atualizar saldo")
        self.balance_refresh_button.clicked.connect(self.refresh_balance)

        self.item_distribution_combo = QComboBox()
        self.item_distribution_button = QPushButton("Ver distribuicao")
        self.item_distribution_button.clicked.connect(self.refresh_item_distribution)

        self.dashboard_page = DashboardPage(self.service)
        self.device_page = (
            DeviceModulePage(self.service, import_devices_callback=self.open_device_import)
            if device_module_enabled
            else None
        )

        self._build_tabs()
        self._build_menu()
        self.refresh_all()

    def _build_menu(self) -> None:
        database_menu = self.menuBar().addMenu("Base de dados")
        protect_action = database_menu.addAction("Proteger base...")
        protect_action.triggered.connect(self.protect_database)

    def _build_tabs(self) -> None:
        self.tabs.addTab(self.dashboard_page, "Dashboard")

        registration = QWidget()
        registration_layout = QGridLayout(registration)

        countries_box = QGroupBox("Paises")
        countries_layout = QVBoxLayout(countries_box)
        countries_form = QFormLayout()
        countries_form.addRow("Nome", self.country_name_input)
        countries_layout.addLayout(countries_form)
        countries_layout.addWidget(self.country_create_button)
        countries_layout.addWidget(self.countries_list)

        locations_box = QGroupBox("Locais")
        locations_layout = QVBoxLayout(locations_box)
        locations_form = QFormLayout()
        locations_form.addRow("Pais", self.location_country_combo)
        locations_form.addRow("Nome", self.location_name_input)
        locations_layout.addLayout(locations_form)
        locations_layout.addWidget(self.location_create_button)
        locations_layout.addWidget(self.locations_list)

        items_box = QGroupBox("Itens")
        items_layout = QVBoxLayout(items_box)
        items_form = QFormLayout()
        items_form.addRow("Serial", self.item_serial_input)
        items_form.addRow("Nome", self.item_name_input)
        items_layout.addLayout(items_form)
        items_layout.addWidget(self.item_create_button)
        items_layout.addWidget(self.items_list)

        # Stock grid showing item x location quantities
        self._build_stock_table()
        items_layout.addWidget(self.stock_table)

        registration_layout.addWidget(countries_box, 0, 0)
        registration_layout.addWidget(locations_box, 0, 1)
        registration_layout.addWidget(items_box, 1, 0, 1, 2)
        self.tabs.addTab(registration, "Cadastros")

        movements = QWidget()
        movements_layout = QVBoxLayout(movements)
        movement_form = QFormLayout()
        movement_form.addRow("Item", self.movement_item_combo)
        movement_form.addRow("Origem", self.movement_from_location_combo)
        movement_form.addRow("Destino", self.movement_to_location_combo)
        movement_form.addRow("Quantidade", self.movement_quantity_spin)
        movement_form.addRow("Observacao", self.movement_note_input)
        movements_layout.addLayout(movement_form)

        movement_buttons = QHBoxLayout()
        movement_buttons.addWidget(self.add_button)
        movement_buttons.addWidget(self.remove_button)
        movement_buttons.addWidget(self.transfer_button)
        movements_layout.addLayout(movement_buttons)
        movements_layout.addWidget(self.movements_list)
        self.tabs.addTab(movements, "Movimentacoes")

        queries = QWidget()
        queries_layout = QVBoxLayout(queries)

        balance_box = QGroupBox("Saldo por local")
        balance_layout = QFormLayout(balance_box)
        balance_layout.addRow("Local", self.balance_location_combo)
        balance_layout.addRow("Saldo", self.balance_value_label)
        balance_layout.addRow(self.balance_refresh_button)

        distribution_box = QGroupBox("Distribuicao por item")
        distribution_layout = QFormLayout(distribution_box)
        distribution_layout.addRow("Item", self.item_distribution_combo)
        distribution_layout.addRow(self.item_distribution_button)

        queries_layout.addWidget(balance_box)
        queries_layout.addWidget(distribution_box)
        queries_layout.addWidget(self.stock_distribution_list)
        self.tabs.addTab(queries, "Consultas")

        if self.device_page is not None:
            self.tabs.addTab(self.device_page, "Devices")

        self.about_page = AboutPage()
        self.tabs.addTab(self.about_page, "Sobre")

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(self.tabs)
        root_layout.addWidget(QLabel("Status"))
        root_layout.addWidget(self.status_area)
        self.setCentralWidget(root)

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "ItemControl", message)

    def show_info(self, message: str) -> None:
        self.status_area.append(message)

    def open_device_import(self) -> None:
        if not self.device_module_enabled or not self.service.repository.has_device_schema():
            self.show_error("A estrutura de Devices nao esta habilitada nesta base.")
            return
        dialog = DeviceCsvImportDialog(self.service, self)
        dialog.exec()
        if dialog.imported_count > 0:
            self.refresh_all()
            self.show_info(f"{dialog.imported_count} devices importados via CSV.")

    def protect_database(self) -> None:
        if self.database_password:
            self.show_error("Esta base ja esta protegida por senha.")
            return

        target, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar copia protegida",
            "",
            "SQLite databases (*.sqlite3 *.db);;All files (*)",
        )
        if not target:
            return
        if str(target) == str(self.database_path):
            self.show_error("Escolha um arquivo diferente da base atual.")
            return

        password_dialog = PasswordConfirmationDialog(self)
        if password_dialog.exec() != QDialog.Accepted:
            return
        password = password_dialog.password()

        try:
            encrypt_plaintext_database(self.database_path, target, password)
        except ItemControlError as exc:
            self.show_error(str(exc))
            return

        add_recent_database(target)
        answer = QMessageBox.question(
            self,
            "ItemControl",
            "Copia protegida criada com sucesso. Deseja abrir essa base agora?",
        )
        if answer != QMessageBox.Yes:
            self.show_info("Copia protegida criada com sucesso.")
            return

        try:
            self.service.repository.close()
            repository = SQLiteRepository(target, password)
            self.service = InventoryService(repository)
            self.dashboard_page.set_service(self.service)
            if self.device_page is not None:
                self.device_page.set_service(self.service)
        except ItemControlError as exc:
            self.show_error(str(exc))
            return
        self.database_path = target
        self.database_password = password
        self.setWindowTitle(f"ItemControl - {target}")
        self.refresh_all()
        self.show_info("Base protegida aberta com sucesso.")

    def _selected_id(self, combo: QComboBox) -> int | None:
        data = combo.currentData()
        return None if data is None else int(data)

    def _load_combo(self, combo: QComboBox, rows, label_builder) -> None:
        current = combo.currentData()
        combo.clear()
        for row in rows:
            combo.addItem(label_builder(row), row["id"])
        if current is not None:
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)

    def refresh_all(self) -> None:
        countries = self.service.countries()
        locations = self.service.locations()
        items = self.service.items()
        movements = self.service.movements()

        self.countries_list.clear()
        for row in countries:
            self.countries_list.addItem(f"#{row['id']} {row['name']}")

        self.locations_list.clear()
        for row in locations:
            self.locations_list.addItem(
                f"#{row['id']} {row['country_name']} / {row['name']}"
            )

        self.items_list.clear()
        for row in items:
            serial = row["serial"] if row["serial"] else "(sem serial)"
            self.items_list.addItem(
                f"#{row['id']} {serial} - {row['name']} [Total: {row['total_quantity']}]"
            )

        self.movements_list.clear()
        for row in movements:
            origin = row["from_location_name"] or "-"
            destination = row["to_location_name"] or "-"
            serial = row["item_serial"] if row["item_serial"] else "(sem serial)"
            self.movements_list.addItem(
                f"#{row['id']} {row['movement_type']} x{row['quantity']} | {serial} | {origin} -> {destination} | {row['created_at']}"
            )

        self._load_combo(self.location_country_combo, countries, lambda r: r["name"])
        self._load_combo(
            self.movement_item_combo,
            items,
            lambda r: f"{r['serial'] or '(sem serial)'} - {r['name']}",
        )
        self._load_combo(
            self.movement_from_location_combo,
            locations,
            lambda r: f"{r['country_name']} - {r['name']}",
        )
        self._load_combo(
            self.movement_to_location_combo,
            locations,
            lambda r: f"{r['country_name']} - {r['name']}",
        )
        self._load_combo(
            self.balance_location_combo,
            locations,
            lambda r: f"{r['country_name']} - {r['name']}",
        )
        self._load_combo(
            self.item_distribution_combo,
            items,
            lambda r: f"{r['serial'] or '(sem serial)'} - {r['name']}",
        )

        self.dashboard_page.load_options(countries, locations)
        self.dashboard_page.refresh()
        if self.device_page is not None:
            self.device_page.refresh()
        self.refresh_balance()
        self.refresh_item_distribution()
        self.refresh_stock_table()

    def refresh_balance(self) -> None:
        location_id = self._selected_id(self.balance_location_combo)
        if location_id is None:
            self.balance_value_label.setText("0")
            return
        try:
            balance = self.service.location_balance(location_id)
        except ItemControlError as exc:
            self.show_error(str(exc))
            return
        self.balance_value_label.setText(str(balance))

    def refresh_item_distribution(self) -> None:
        item_id = self._selected_id(self.item_distribution_combo)
        self.stock_distribution_list.clear()
        if item_id is None:
            return
        try:
            stock_rows = self.service.stock_for_item(item_id)
        except ItemControlError as exc:
            self.show_error(str(exc))
            return

        if not stock_rows:
            self.stock_distribution_list.addItem("Sem saldo em nenhum local")
            return

        for row in stock_rows:
            self.stock_distribution_list.addItem(
                f"{row['country_name']} / {row['location_name']}: {row['quantity']}"
            )

    def _build_stock_table(self) -> None:
        self.stock_table.setColumnCount(6)
        self.stock_table.setHorizontalHeaderLabels(
            ["Item ID", "Serial", "Item", "Country", "Location", "Quantity"]
        )
        self.stock_table.setSortingEnabled(True)
        self.stock_table.setMinimumHeight(200)

    def refresh_stock_table(self) -> None:
        try:
            items = self.service.items()
        except ItemControlError as exc:
            self.show_error(str(exc))
            return

        rows = []
        for item in items:
            stock_rows = self.service.stock_for_item(item["id"]) or []
            if not stock_rows:
                rows.append(
                    (
                        item["id"],
                        item["serial"] or "(sem serial)",
                        item["name"],
                        "-",
                        "-",
                        "0",
                    )
                )
            else:
                for s in stock_rows:
                    rows.append(
                        (
                            item["id"],
                            item["serial"] or "(sem serial)",
                            item["name"],
                            s["country_name"],
                            s["location_name"],
                            str(s["quantity"]),
                        )
                    )

        self.stock_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, value in enumerate(row):
                self.stock_table.setItem(r_idx, c_idx, QTableWidgetItem(str(value)))

    def create_country(self) -> None:
        try:
            self.service.create_country(self.country_name_input.text())
            self.country_name_input.clear()
            self.refresh_all()
            self.show_info("Pais cadastrado com sucesso.")
        except ItemControlError as exc:
            self.show_error(str(exc))

    def create_location(self) -> None:
        country_id = self._selected_id(self.location_country_combo)
        if country_id is None:
            self.show_error("Cadastre um pais antes de criar um local.")
            return
        try:
            self.service.create_location(country_id, self.location_name_input.text())
            self.location_name_input.clear()
            self.refresh_all()
            self.show_info("Local cadastrado com sucesso.")
        except ItemControlError as exc:
            self.show_error(str(exc))

    def create_item(self) -> None:
        try:
            self.service.create_item(
                self.item_serial_input.text(), self.item_name_input.text()
            )
            self.item_serial_input.clear()
            self.item_name_input.clear()
            self.refresh_all()
            self.show_info("Item cadastrado com sucesso.")
        except ItemControlError as exc:
            self.show_error(str(exc))

    def add_item(self) -> None:
        item_id = self._selected_id(self.movement_item_combo)
        to_location_id = self._selected_id(self.movement_to_location_combo)
        quantity = self.movement_quantity_spin.value()
        if item_id is None or to_location_id is None:
            self.show_error("Selecione item e local de destino.")
            return
        try:
            self.service.add_item_to_location(
                item_id,
                to_location_id,
                quantity=quantity,
                note=self.movement_note_input.text(),
            )
            self.refresh_all()
            self.show_info("Saldo adicionado com sucesso.")
        except ItemControlError as exc:
            self.show_error(str(exc))

    def remove_item(self) -> None:
        item_id = self._selected_id(self.movement_item_combo)
        from_location_id = self._selected_id(self.movement_from_location_combo)
        quantity = self.movement_quantity_spin.value()
        if item_id is None or from_location_id is None:
            self.show_error("Selecione item e local de origem.")
            return
        try:
            self.service.remove_item_from_location(
                item_id,
                from_location_id,
                quantity=quantity,
                note=self.movement_note_input.text(),
            )
            self.refresh_all()
            self.show_info("Saldo retirado com sucesso.")
        except ItemControlError as exc:
            self.show_error(str(exc))

    def transfer_item(self) -> None:
        item_id = self._selected_id(self.movement_item_combo)
        from_location_id = self._selected_id(self.movement_from_location_combo)
        to_location_id = self._selected_id(self.movement_to_location_combo)
        quantity = self.movement_quantity_spin.value()
        if item_id is None or from_location_id is None or to_location_id is None:
            self.show_error("Selecione item, origem e destino.")
            return
        try:
            self.service.transfer_item(
                item_id,
                from_location_id,
                to_location_id,
                quantity=quantity,
                note=self.movement_note_input.text(),
            )
            self.refresh_all()
            self.show_info("Transferencia realizada com sucesso.")
        except ItemControlError as exc:
            self.show_error(str(exc))


def build_application(
    database_path: str = "itemcontrol.sqlite3",
    database_password: str | None = None,
) -> tuple[QApplication, MainWindow | None]:
    app = QApplication.instance() or QApplication(sys.argv)
    if database_path == "itemcontrol.sqlite3" and database_password is None:
        dialog = DatabaseSelectionDialog()
        if dialog.exec() != QDialog.Accepted or dialog.database_path is None:
            return app, None
        database_path = dialog.database_path
        database_password = dialog.database_password
    repository = SQLiteRepository(database_path, database_password)
    device_module_enabled = True
    if repository.device_schema_needs_upgrade():
        missing_tables = repository.device_schema_missing_tables()
        current_version = repository.device_schema_version()
        version_text = "nenhuma" if current_version is None else str(current_version)
        answer = QMessageBox.question(
            None,
            "ItemControl",
            "A base selecionada nao possui a estrutura de Devices.\n\n"
            "Versao atual da estrutura: "
            + version_text
            + "\nVersao esperada: "
            + str(DEVICE_MODULE_VERSION)
            + "\nTabelas faltando: "
            + (", ".join(missing_tables) if missing_tables else "nenhuma")
            + "\n\nDeseja criar/atualizar agora?",
        )
        if answer == QMessageBox.Yes:
            repository.ensure_device_schema()
        else:
            device_module_enabled = False
    service = InventoryService(repository)
    window = MainWindow(
        service,
        database_path,
        database_password,
        device_module_enabled=device_module_enabled,
    )
    return app, window


def main() -> int:
    app, window = build_application()
    if window is None:
        return 0
    window.show()
    return app.exec()
