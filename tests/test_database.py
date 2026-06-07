import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itemcontrol.database import encrypt_plaintext_database
from itemcontrol.domain import DatabaseOpenError
from itemcontrol.repository import SQLiteRepository
from itemcontrol.service import InventoryService
from itemcontrol.settings import add_recent_database, load_recent_databases


SQLCIPHER_AVAILABLE = importlib.util.find_spec("sqlcipher3") is not None


class DatabaseSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _seed_plain_database(self, path: Path) -> None:
        repository = SQLiteRepository(path)
        service = InventoryService(repository)
        country_id = service.create_country("Brazil")
        location_a = service.create_location(country_id, "SP")
        location_b = service.create_location(country_id, "RJ")
        item_id = service.create_item("SER-100", "Notebook")
        service.add_item_to_location(item_id, location_a, quantity=5)
        service.transfer_item(item_id, location_a, location_b, quantity=2)
        repository.close()

    def test_plain_database_opens_without_sqlcipher(self) -> None:
        database_path = self.root / "plain.sqlite3"
        with patch("itemcontrol.database._load_sqlcipher") as load_sqlcipher:
            repository = SQLiteRepository(database_path)
            service = InventoryService(repository)
            service.create_country("Brazil")
            repository.close()
        load_sqlcipher.assert_not_called()

    def test_recent_databases_do_not_store_passwords(self) -> None:
        settings_path = self.root / "settings.json"
        database_path = self.root / "inventory.sqlite3"

        recent = add_recent_database(database_path, path=settings_path)

        self.assertEqual(recent, [str(database_path.resolve())])
        self.assertEqual(load_recent_databases(settings_path), recent)
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertNotIn("password", json.dumps(data).lower())

    @unittest.skipUnless(SQLCIPHER_AVAILABLE, "sqlcipher3 is not installed")
    def test_encrypted_database_opens_with_correct_password(self) -> None:
        database_path = self.root / "encrypted.sqlite3"
        repository = SQLiteRepository(database_path, password="secret")
        service = InventoryService(repository)
        service.create_country("Brazil")
        repository.close()

        repository = SQLiteRepository(database_path, password="secret")
        self.assertEqual(len(repository.list_countries()), 1)
        repository.close()

    @unittest.skipUnless(SQLCIPHER_AVAILABLE, "sqlcipher3 is not installed")
    def test_encrypted_database_rejects_wrong_password(self) -> None:
        database_path = self.root / "encrypted.sqlite3"
        repository = SQLiteRepository(database_path, password="secret")
        repository.close()

        with self.assertRaises(DatabaseOpenError):
            SQLiteRepository(database_path, password="wrong")

    @unittest.skipUnless(SQLCIPHER_AVAILABLE, "sqlcipher3 is not installed")
    def test_sqlite3_cannot_read_encrypted_database(self) -> None:
        database_path = self.root / "encrypted.sqlite3"
        repository = SQLiteRepository(database_path, password="secret")
        repository.close()

        connection = sqlite3.connect(database_path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        finally:
            connection.close()

    @unittest.skipUnless(SQLCIPHER_AVAILABLE, "sqlcipher3 is not installed")
    def test_plain_database_exports_to_encrypted_copy(self) -> None:
        plain_path = self.root / "plain.sqlite3"
        encrypted_path = self.root / "protected.sqlite3"
        self._seed_plain_database(plain_path)

        encrypt_plaintext_database(plain_path, encrypted_path, "secret")

        repository = SQLiteRepository(encrypted_path, password="secret")
        service = InventoryService(repository)
        self.assertEqual(len(service.countries()), 1)
        self.assertEqual(len(service.locations()), 2)
        self.assertEqual(len(service.items()), 1)
        self.assertEqual(service.total_in_inventory(), 5)
        self.assertEqual(len(service.movements()), 2)
        repository.close()


if __name__ == "__main__":
    unittest.main()
