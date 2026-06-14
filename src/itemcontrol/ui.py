from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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
from .repository import SQLiteRepository
from .service import InventoryService
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
    ) -> None:
        super().__init__()
        self.service = service
        self.database_path = database_path
        self.database_password = database_password
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
    service = InventoryService(repository)
    window = MainWindow(service, database_path, database_password)
    return app, window


def main() -> int:
    app, window = build_application()
    if window is None:
        return 0
    window.show()
    return app.exec()
