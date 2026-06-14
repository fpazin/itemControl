import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itemcontrol.domain import ValidationError
from itemcontrol.repository import SQLiteRepository
from itemcontrol.service import InventoryService


class InventoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "test.sqlite3"
        self.repository = SQLiteRepository(self.database_path)
        self.service = InventoryService(self.repository)

    def tearDown(self) -> None:
        self.repository.close()
        self.tempdir.cleanup()

    def _setup_locations(self):
        country_id = self.service.create_country("Brazil")
        loc_sp = self.service.create_location(country_id, "SP")
        loc_rj = self.service.create_location(country_id, "RJ")
        return loc_sp, loc_rj

    def test_item_can_exist_in_multiple_locations(self) -> None:
        loc_sp, loc_rj = self._setup_locations()
        item_id = self.service.create_item("SER-001", "Notebook")

        self.service.add_item_to_location(item_id, loc_sp, quantity=5)
        self.service.add_item_to_location(item_id, loc_rj, quantity=3)

        self.assertEqual(self.service.location_balance(loc_sp), 5)
        self.assertEqual(self.service.location_balance(loc_rj), 3)
        self.assertEqual(self.service.total_in_inventory(), 8)

    def test_transfer_keeps_global_total(self) -> None:
        loc_sp, loc_rj = self._setup_locations()
        item_id = self.service.create_item("SER-002", "Monitor")

        self.service.add_item_to_location(item_id, loc_sp, quantity=10)
        before_total = self.service.total_in_inventory()

        self.service.transfer_item(item_id, loc_sp, loc_rj, quantity=4)

        self.assertEqual(self.service.location_balance(loc_sp), 6)
        self.assertEqual(self.service.location_balance(loc_rj), 4)
        self.assertEqual(self.service.total_in_inventory(), before_total)

    def test_remove_blocks_when_insufficient_stock(self) -> None:
        loc_sp, _ = self._setup_locations()
        item_id = self.service.create_item("SER-003", "Dock")

        self.service.add_item_to_location(item_id, loc_sp, quantity=2)

        with self.assertRaises(ValidationError):
            self.service.remove_item_from_location(item_id, loc_sp, quantity=3)

    def test_transfer_blocks_when_insufficient_stock(self) -> None:
        loc_sp, loc_rj = self._setup_locations()
        item_id = self.service.create_item("SER-004", "Mouse")

        self.service.add_item_to_location(item_id, loc_sp, quantity=1)

        with self.assertRaises(ValidationError):
            self.service.transfer_item(item_id, loc_sp, loc_rj, quantity=2)

    def test_serial_is_optional_but_unique_when_present(self) -> None:
        self.service.create_item(None, "Cable A")
        self.service.create_item(None, "Cable B")

        self.service.create_item("SER-005", "Keyboard")
        with self.assertRaises(ValidationError):
            self.service.create_item("SER-005", "Keyboard Clone")

    def test_dashboard_aggregates_and_filters_positive_stock(self) -> None:
        brazil_id = self.service.create_country("Brazil")
        us_id = self.service.create_country("United States")
        sp_id = self.service.create_location(brazil_id, "Sao Paulo")
        rio_id = self.service.create_location(brazil_id, "Rio de Janeiro")
        ny_id = self.service.create_location(us_id, "New York")
        notebook_id = self.service.create_item("NOTE-001", "Notebook")
        monitor_id = self.service.create_item("MON-001", "Monitor")
        self.service.create_item("ZERO-001", "Item sem estoque")

        self.service.add_item_to_location(notebook_id, sp_id, quantity=5)
        self.service.add_item_to_location(notebook_id, rio_id, quantity=3)
        self.service.add_item_to_location(monitor_id, ny_id, quantity=2)

        result = self.service.dashboard()
        self.assertEqual(result["total_units"], 10)
        self.assertEqual(result["distinct_items"], 2)
        self.assertEqual(result["countries"], 2)
        self.assertEqual(result["locations"], 3)
        self.assertEqual(len(result["details"]), 3)
        self.assertEqual(
            [(row["name"], row["quantity"]) for row in result["by_country"]],
            [("Brazil", 8), ("United States", 2)],
        )

        brazil = self.service.dashboard(country_id=brazil_id)
        self.assertEqual(brazil["total_units"], 8)
        self.assertEqual(brazil["locations"], 2)

        sao_paulo = self.service.dashboard(location_id=sp_id)
        self.assertEqual(sao_paulo["total_units"], 5)
        self.assertEqual(len(sao_paulo["details"]), 1)

        by_name = self.service.dashboard(item_query="NOTE")
        self.assertEqual(by_name["total_units"], 8)
        by_serial = self.service.dashboard(item_query="mon-001")
        self.assertEqual(by_serial["total_units"], 2)

    def test_dashboard_returns_only_ten_highest_stock_locations(self) -> None:
        country_id = self.service.create_country("Brazil")
        item_id = self.service.create_item("RANK-001", "Ranking")
        for index in range(11):
            location_id = self.service.create_location(
                country_id, f"Location {index + 1:02d}"
            )
            self.service.add_item_to_location(
                item_id, location_id, quantity=index + 1
            )

        result = self.service.dashboard()
        self.assertEqual(len(result["by_location"]), 10)
        self.assertEqual(result["by_location"][0]["quantity"], 11)
        self.assertEqual(result["by_location"][-1]["quantity"], 2)


if __name__ == "__main__":
    unittest.main()
