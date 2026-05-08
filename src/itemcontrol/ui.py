from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .domain import ItemControlError
from .repository import SQLiteRepository
from .service import InventoryService


class MainWindow(QMainWindow):
    def __init__(self, service: InventoryService) -> None:
        super().__init__()
        self.service = service
        self.setWindowTitle("ItemControl")
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

        self._build_tabs()
        self.refresh_all()

    def _build_tabs(self) -> None:
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
) -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = SQLiteRepository(database_path)
    service = InventoryService(repository)
    window = MainWindow(service)
    return app, window


def main() -> int:
    app, window = build_application()
    window.show()
    return app.exec()
