import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication

from itemcontrol.repository import SQLiteRepository
from itemcontrol.service import InventoryService
from itemcontrol.ui import MainWindow


class DashboardPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = SQLiteRepository(
            Path(self.tempdir.name) / "dashboard.sqlite3"
        )
        self.service = InventoryService(self.repository)
        self.brazil_id = self.service.create_country("Brazil")
        self.us_id = self.service.create_country("United States")
        self.sp_id = self.service.create_location(self.brazil_id, "Sao Paulo")
        self.ny_id = self.service.create_location(self.us_id, "New York")
        self.notebook_id = self.service.create_item("NOTE-001", "Notebook")
        self.service.add_item_to_location(self.notebook_id, self.sp_id, quantity=4)
        self.window = MainWindow(
            self.service, str(Path(self.tempdir.name) / "dashboard.sqlite3")
        )

    def tearDown(self) -> None:
        self.window.close()
        self.repository.close()
        self.tempdir.cleanup()

    def test_dashboard_is_first_tab_with_indicators_charts_and_table(self) -> None:
        page = self.window.dashboard_page
        self.assertEqual(self.window.tabs.tabText(0), "Dashboard")
        self.assertIn("4", page.total_units_label.text())
        self.assertEqual(page.stock_table.rowCount(), 1)
        self.assertEqual(len(page.country_chart.chart().series()), 1)
        self.assertEqual(len(page.location_chart.chart().series()), 1)

    def test_country_filter_limits_locations_and_clear_restores_filters(self) -> None:
        page = self.window.dashboard_page
        page.country_combo.setCurrentIndex(
            page.country_combo.findData(self.brazil_id)
        )

        self.assertEqual(page.location_combo.count(), 2)
        self.assertEqual(page.location_combo.itemData(1), self.sp_id)

        page.item_query_input.setText("missing")
        page.refresh()
        self.assertFalse(page.empty_label.isHidden())
        self.assertTrue(page.stock_table.isHidden())
        self.assertIn("0", page.total_units_label.text())

        page.clear_filters()
        self.assertIsNone(page.country_combo.currentData())
        self.assertIsNone(page.location_combo.currentData())
        self.assertEqual(page.item_query_input.text(), "")
        self.assertEqual(page.stock_table.rowCount(), 1)

    def test_refresh_all_updates_dashboard_after_stock_change(self) -> None:
        self.service.add_item_to_location(self.notebook_id, self.ny_id, quantity=3)
        self.window.refresh_all()

        page = self.window.dashboard_page
        self.assertIn("7", page.total_units_label.text())
        self.assertEqual(page.stock_table.rowCount(), 2)

    def test_dashboard_device_tab_uses_same_filters(self) -> None:
        self.repository.ensure_device_schema()
        device_type_id = next(
            row["id"] for row in self.service.device_types() if row["name"] == "Desktop"
        )
        user_id = self.service.create_device_user("Alice")
        device_id = self.service.create_device(
            "DEV-001",
            "Notebook corporativo",
            device_type_id,
            "Em uso",
            self.sp_id,
            user_id,
        )
        self.window.refresh_all()

        page = self.window.dashboard_page
        self.assertEqual(page.dashboard_tabs.tabText(1), "Devices")
        self.assertEqual(page.device_table.rowCount(), 1)
        self.assertIn("DEV-001", page.device_table.item(0, 0).text())

        page.country_combo.setCurrentIndex(page.country_combo.findData(self.brazil_id))
        page.item_query_input.setText("Macbook")
        page.refresh()
        self.assertEqual(page.device_table.rowCount(), 0)
        self.assertFalse(page.device_empty_label.isHidden())


if __name__ == "__main__":
    unittest.main()
