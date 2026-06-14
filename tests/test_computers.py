import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication, QMessageBox

from itemcontrol.domain import ValidationError
from itemcontrol.repository import DEVICE_SCHEMA_TABLES, SQLiteRepository
from itemcontrol.service import InventoryService
from itemcontrol.ui import build_application


class ComputerModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "computers.sqlite3"
        self.repository = SQLiteRepository(self.database_path)
        self.service = InventoryService(self.repository)

    def tearDown(self) -> None:
        self.repository.close()
        self.tempdir.cleanup()

    def test_schema_analysis_reports_missing_tables_until_created(self) -> None:
        self.assertFalse(self.repository.has_device_schema())
        self.assertCountEqual(
            self.repository.device_schema_missing_tables(),
            DEVICE_SCHEMA_TABLES,
        )

        self.repository.ensure_device_schema()
        self.assertTrue(self.repository.has_device_schema())
        self.assertEqual(self.repository.device_schema_missing_tables(), [])

    def test_default_device_types_are_seeded_and_more_can_be_added(self) -> None:
        self.repository.ensure_device_schema()
        seeded = [row["name"] for row in self.service.device_types()]
        self.assertIn("Desktop", seeded)
        self.service.create_device_type("Notebook")
        self.assertIn("Notebook", [row["name"] for row in self.service.device_types()])

    def test_available_device_requires_only_location(self) -> None:
        self.repository.ensure_device_schema()
        country_id = self.service.create_country("Brazil")
        location_id = self.service.create_location(country_id, "HQ")
        type_id = next(
            row["id"] for row in self.service.device_types() if row["name"] == "Desktop"
        )
        device_id = self.service.create_device(
            "PC-001",
            "Notebook",
            type_id,
            "Disponível",
            location_id,
        )

        device = self.repository.get_device(device_id)
        self.assertEqual(device["status"], "Disponível")
        self.assertIsNone(device["user_id"])

    def test_transfer_requires_user_unless_device_is_available(self) -> None:
        self.repository.ensure_device_schema()
        user_a = self.service.create_device_user("Alice")
        user_b = self.service.create_device_user("Bob")
        country_id = self.service.create_country("Brazil")
        location_a = self.service.create_location(country_id, "Desk 1")
        location_b = self.service.create_location(country_id, "Desk 2")
        type_id = next(
            row["id"] for row in self.service.device_types() if row["name"] == "Macbook"
        )
        device_id = self.service.create_device(
            "PC-002",
            "Desktop",
            type_id,
            "Em uso",
            location_a,
            user_a,
        )

        with self.assertRaises(ValidationError):
            self.service.transfer_device(device_id, location_b)

        self.service.transfer_device(
            device_id,
            location_b,
            user_b,
            "Em uso",
            "Nova alocacao",
        )
        device = self.repository.get_device(device_id)
        self.assertEqual(device["location_id"], location_b)
        self.assertEqual(device["user_id"], user_b)
        self.assertEqual(device["status"], "Em uso")
        self.assertEqual(len(self.service.device_transfers()), 1)

    def test_build_application_prompts_and_enables_device_module(self) -> None:
        with patch("itemcontrol.ui.QMessageBox.question", return_value=QMessageBox.Yes):
            app, window = build_application(str(self.database_path))

        self.assertIsNotNone(window)
        self.assertTrue(window.device_module_enabled)
        self.assertTrue(window.service.repository.has_device_schema())
        self.assertIn("Devices", [window.tabs.tabText(i) for i in range(window.tabs.count())])

        window.close()
        window.service.repository.close()
        app.quit()


if __name__ == "__main__":
    unittest.main()
