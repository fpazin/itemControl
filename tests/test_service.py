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


if __name__ == "__main__":
    unittest.main()
