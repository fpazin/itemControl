import importlib.metadata
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itemcontrol import __version__
from itemcontrol.about import about_details
from itemcontrol.ui import MainWindow


class AboutPageTests(unittest.TestCase):
    def test_about_tab_displays_version_and_developer(self) -> None:
        tab_source = inspect.getsource(MainWindow._build_tabs)
        details = about_details()

        self.assertIn('self.tabs.addTab(self.about_page, "Sobre")', tab_source)
        self.assertEqual(details["name"], "ItemControl")
        self.assertEqual(details["version"], __version__)
        self.assertEqual(details["developer"], "Felipe Pazin")

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
