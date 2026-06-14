from __future__ import annotations

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .service import InventoryService


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        return int(self.data(Qt.UserRole)) < int(other.data(Qt.UserRole))


class DashboardPage(QWidget):
    def __init__(
        self, service: InventoryService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.service = service
        self._locations: list[dict] = []

        self.country_combo = QComboBox()
        self.location_combo = QComboBox()
        self.item_query_input = QLineEdit()
        self.item_query_input.setPlaceholderText("Nome ou serial")
        self.refresh_button = QPushButton("Atualizar")
        self.clear_button = QPushButton("Limpar filtros")

        self.total_units_label = self._indicator("0", "Unidades em estoque")
        self.distinct_items_label = self._indicator("0", "Equipamentos")
        self.countries_label = self._indicator("0", "Paises")
        self.locations_label = self._indicator("0", "Locais")

        self.country_chart = QChartView()
        self.location_chart = QChartView()
        for chart_view in (self.country_chart, self.location_chart):
            chart_view.setRenderHint(QPainter.Antialiasing)
            chart_view.setMinimumHeight(230)

        self.stock_table = QTableWidget(0, 5)
        self.stock_table.setHorizontalHeaderLabels(
            ["Serial", "Equipamento", "Pais", "Local", "Quantidade"]
        )
        self.stock_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stock_table.setSortingEnabled(True)
        header = self.stock_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.device_table = QTableWidget(0, 7)
        self.device_table.setHorizontalHeaderLabels(
            ["Serial", "Device", "Tipo", "Status", "Usuario", "Pais", "Local"]
        )
        self.device_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.device_table.setSortingEnabled(True)
        device_header = self.device_table.horizontalHeader()
        device_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        device_header.setSectionResizeMode(1, QHeaderView.Stretch)
        device_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.empty_label = QLabel("Nenhum estoque encontrado para os filtros aplicados.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #666; padding: 16px;")

        self.device_empty_label = QLabel(
            "Nenhum device encontrado para os filtros aplicados."
        )
        self.device_empty_label.setAlignment(Qt.AlignCenter)
        self.device_empty_label.setStyleSheet("color: #666; padding: 16px;")

        self.dashboard_tabs = QTabWidget()

        self._build_layout()
        self.country_combo.currentIndexChanged.connect(self._country_changed)
        self.refresh_button.clicked.connect(self.refresh)
        self.clear_button.clicked.connect(self.clear_filters)
        self.item_query_input.returnPressed.connect(self.refresh)

    @staticmethod
    def _indicator(value: str, title: str) -> QLabel:
        label = QLabel(f"<b style='font-size: 22px'>{value}</b><br>{title}")
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumHeight(72)
        label.setStyleSheet("border: 1px solid #c8ccd0; padding: 8px;")
        return label

    def _build_layout(self) -> None:
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Pais"))
        filters.addWidget(self.country_combo)
        filters.addWidget(QLabel("Local"))
        filters.addWidget(self.location_combo)
        filters.addWidget(QLabel("Equipamento"))
        filters.addWidget(self.item_query_input, 1)
        filters.addWidget(self.refresh_button)
        filters.addWidget(self.clear_button)

        indicators = QGridLayout()
        indicators.addWidget(self.total_units_label, 0, 0)
        indicators.addWidget(self.distinct_items_label, 0, 1)
        indicators.addWidget(self.countries_label, 0, 2)
        indicators.addWidget(self.locations_label, 0, 3)

        charts = QHBoxLayout()
        charts.addWidget(self.country_chart, 1)
        charts.addWidget(self.location_chart, 1)

        stock_page = QWidget()
        stock_layout = QVBoxLayout(stock_page)
        stock_layout.addWidget(self.empty_label)
        stock_layout.addWidget(self.stock_table, 1)

        devices_page = QWidget()
        devices_layout = QVBoxLayout(devices_page)
        devices_layout.addWidget(self.device_empty_label)
        devices_layout.addWidget(self.device_table, 1)

        self.dashboard_tabs.addTab(stock_page, "Estoque")
        self.dashboard_tabs.addTab(devices_page, "Devices")

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addLayout(indicators)
        layout.addLayout(charts)
        layout.addWidget(self.dashboard_tabs, 1)

    def set_service(self, service: InventoryService) -> None:
        self.service = service

    def load_options(self, countries, locations) -> None:
        selected_country = self.country_combo.currentData()
        self.country_combo.blockSignals(True)
        self.country_combo.clear()
        self.country_combo.addItem("Todos", None)
        for country in countries:
            self.country_combo.addItem(country["name"], country["id"])
        if selected_country is not None:
            index = self.country_combo.findData(selected_country)
            if index >= 0:
                self.country_combo.setCurrentIndex(index)
        self.country_combo.blockSignals(False)
        self._locations = list(locations)
        self._reload_locations()

    def _country_changed(self) -> None:
        self._reload_locations()
        self.refresh()

    def _reload_locations(self) -> None:
        selected_location = self.location_combo.currentData()
        country_id = self.country_combo.currentData()
        self.location_combo.clear()
        self.location_combo.addItem("Todos", None)
        for location in self._locations:
            if country_id is None or location["country_id"] == country_id:
                self.location_combo.addItem(
                    f"{location['country_name']} - {location['name']}",
                    location["id"],
                )
        if selected_location is not None:
            index = self.location_combo.findData(selected_location)
            if index >= 0:
                self.location_combo.setCurrentIndex(index)

    def clear_filters(self) -> None:
        self.country_combo.setCurrentIndex(0)
        self.location_combo.setCurrentIndex(0)
        self.item_query_input.clear()
        self.refresh()

    def refresh(self) -> None:
        result = self.service.dashboard(
            country_id=self.country_combo.currentData(),
            location_id=self.location_combo.currentData(),
            item_query=self.item_query_input.text(),
        )
        device_result = self.service.dashboard_devices(
            country_id=self.country_combo.currentData(),
            location_id=self.location_combo.currentData(),
            device_query=self.item_query_input.text(),
        )
        self._set_indicator(
            self.total_units_label, result["total_units"], "Unidades em estoque"
        )
        self._set_indicator(
            self.distinct_items_label, result["distinct_items"], "Equipamentos"
        )
        self._set_indicator(self.countries_label, result["countries"], "Paises")
        self._set_indicator(self.locations_label, result["locations"], "Locais")
        self.country_chart.setChart(
            self._bar_chart("Estoque por pais", result["by_country"], "name")
        )
        self.location_chart.setChart(
            self._bar_chart(
                "10 locais com maior estoque", result["by_location"], "label"
            )
        )
        self._fill_table(result["details"])
        has_rows = bool(result["details"])
        self.empty_label.setVisible(not has_rows)
        self.stock_table.setVisible(has_rows)
        self._fill_device_table(device_result["details"])
        has_device_rows = bool(device_result["details"])
        self.device_empty_label.setVisible(not has_device_rows)
        self.device_table.setVisible(has_device_rows)

    @staticmethod
    def _set_indicator(label: QLabel, value: int, title: str) -> None:
        label.setText(f"<b style='font-size: 22px'>{value}</b><br>{title}")

    @staticmethod
    def _bar_chart(title: str, rows: list[dict], label_key: str) -> QChart:
        chart = QChart()
        chart.setTitle(title)
        chart.legend().hide()
        if not rows:
            return chart

        bar_set = QBarSet("Quantidade")
        bar_set.append([row["quantity"] for row in rows])
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)

        categories = [row[label_key] for row in rows]
        category_axis = QBarCategoryAxis()
        category_axis.append(categories)
        chart.addAxis(category_axis, Qt.AlignBottom)
        series.attachAxis(category_axis)

        value_axis = QValueAxis()
        value_axis.setLabelFormat("%d")
        value_axis.setRange(0, max(row["quantity"] for row in rows))
        chart.addAxis(value_axis, Qt.AlignLeft)
        series.attachAxis(value_axis)
        return chart

    def _fill_table(self, rows) -> None:
        self.stock_table.setSortingEnabled(False)
        self.stock_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row["serial"] or "(sem serial)",
                row["item_name"],
                row["country_name"],
                row["location_name"],
            )
            for column, value in enumerate(values):
                self.stock_table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )
            quantity_item = NumericTableWidgetItem(str(row["quantity"]))
            quantity_item.setData(Qt.UserRole, int(row["quantity"]))
            self.stock_table.setItem(row_index, 4, quantity_item)
        self.stock_table.setSortingEnabled(True)

    def _fill_device_table(self, rows) -> None:
        self.device_table.setSortingEnabled(False)
        self.device_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                row["serial"] or "(sem serial)",
                row["device_name"],
                row["device_type_name"],
                row["status"],
                row["user_name"] or "-",
                row["country_name"],
                row["location_name"],
            )
            for column, value in enumerate(values):
                self.device_table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )
        self.device_table.setSortingEnabled(True)
