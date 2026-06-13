import importlib.metadata
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication

from itemcontrol import __version__
from itemcontrol.about import about_details
from itemcontrol.repository import SQLiteRepository
from itemcontrol.service import InventoryService
from itemcontrol.ui import MainWindow


class AboutPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        database_path = Path(self.tempdir.name) / "about.sqlite3"
        self.repository = SQLiteRepository(database_path)
        self.window = MainWindow(
            InventoryService(self.repository), str(database_path)
        )

    def tearDown(self) -> None:
        self.window.close()
        self.repository.close()
        self.tempdir.cleanup()

    def test_about_tab_displays_version_and_developer(self) -> None:
        tab_names = [
            self.window.tabs.tabText(index)
            for index in range(self.window.tabs.count())
        ]
        self.assertIn("Sobre", tab_names)
        self.assertEqual(
            self.window.about_page.version_label.text(), f"Versao {__version__}"
        )
        self.assertIn("Felipe Pazin", self.window.about_page.developer_label.text())

    def test_about_links_use_expected_github_urls(self) -> None:
        details = about_details()
        self.assertEqual(details["developer_url"], "https://github.com/fpazin")
        self.assertEqual(
            details["repository_url"], "https://github.com/fpazin/itemControl"
        )
        self.assertEqual(
            details["releases_url"],
            "https://github.com/fpazin/itemControl/releases",
        )

    def test_package_metadata_uses_the_runtime_version(self) -> None:
        self.assertEqual(importlib.metadata.version("itemcontrol"), __version__)


if __name__ == "__main__":
    unittest.main()
