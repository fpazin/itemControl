from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .database import open_database_connection
from .domain import DatabaseOpenError


DEVICE_MODULE_VERSION = 1

DEVICE_STATUSES = (
    "Em uso",
    "Disponível",
    "Decommissionado",
    "Desativado",
)

DEVICE_SCHEMA_TABLES = (
    "device_users",
    "device_types",
    "devices",
    "device_transfers",
)

DEFAULT_DEVICE_TYPES = (
    "Tablet",
    "Desktop",
    "Macbook",
)


def _dict_row_factory(cursor, row):
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


class SQLiteRepository:
    def __init__(
        self,
        database_path: str | Path = "itemcontrol.sqlite3",
        password: str | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.password_protected = bool(password)
        try:
            self.connection = open_database_connection(self.database_path, password)
            self.connection.row_factory = _dict_row_factory
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.ensure_schema()
        except DatabaseOpenError:
            if hasattr(self, "connection"):
                self.connection.close()
            raise
        except Exception as exc:
            if hasattr(self, "connection"):
                self.connection.close()
            raise DatabaseOpenError(f"Could not open database: {exc}") from exc

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        cursor = self.connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def ensure_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(country_id, name),
                FOREIGN KEY(country_id) REFERENCES countries(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial TEXT UNIQUE,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS item_stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                UNIQUE(item_id, location_id),
                FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY(location_id) REFERENCES locations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                from_location_id INTEGER,
                to_location_id INTEGER,
                quantity INTEGER NOT NULL DEFAULT 1,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY(from_location_id) REFERENCES locations(id) ON DELETE SET NULL,
                FOREIGN KEY(to_location_id) REFERENCES locations(id) ON DELETE SET NULL
            );
            """
        )
        self._apply_compat_migrations()
        self.connection.commit()

    def device_schema_version(self) -> int | None:
        try:
            row = self.connection.execute(
                "SELECT value FROM schema_versions WHERE name = 'devices'"
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return int(row["value"]) if row else None

    def device_schema_missing_tables(self) -> list[str]:
        existing_tables = {
            row["name"]
            for row in self.connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name IN (
                    'device_users',
                    'device_types',
                    'devices',
                    'device_transfers'
                )
                """
            ).fetchall()
        }
        return [table for table in DEVICE_SCHEMA_TABLES if table not in existing_tables]

    def has_device_schema(self) -> bool:
        return not self.device_schema_missing_tables()

    def device_schema_needs_upgrade(self) -> bool:
        return self.device_schema_version() != DEVICE_MODULE_VERSION or not self.has_device_schema()

    def ensure_device_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_versions (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS device_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS device_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                device_type_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'Em uso',
                    'Disponível',
                    'Decommissionado',
                    'Desativado'
                )),
                user_id INTEGER,
                location_id INTEGER NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(device_type_id) REFERENCES device_types(id) ON DELETE RESTRICT,
                FOREIGN KEY(user_id) REFERENCES device_users(id) ON DELETE SET NULL,
                FOREIGN KEY(location_id) REFERENCES locations(id) ON DELETE RESTRICT,
                CHECK(
                    (status = 'Disponível' AND user_id IS NULL)
                    OR (status <> 'Disponível' AND user_id IS NOT NULL)
                )
            );

            CREATE TABLE IF NOT EXISTS device_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                from_user_id INTEGER,
                to_user_id INTEGER,
                from_location_id INTEGER,
                to_location_id INTEGER,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE,
                FOREIGN KEY(from_user_id) REFERENCES device_users(id) ON DELETE SET NULL,
                FOREIGN KEY(to_user_id) REFERENCES device_users(id) ON DELETE SET NULL,
                FOREIGN KEY(from_location_id) REFERENCES locations(id) ON DELETE SET NULL,
                FOREIGN KEY(to_location_id) REFERENCES locations(id) ON DELETE SET NULL
            );
            """
        )
        self.connection.execute(
            """
            INSERT INTO schema_versions (name, value)
            VALUES ('devices', ?)
            ON CONFLICT(name) DO UPDATE SET value = excluded.value
            """,
            (DEVICE_MODULE_VERSION,),
        )
        existing_types = {
            row["name"]
            for row in self.connection.execute("SELECT name FROM device_types").fetchall()
        }
        for device_type in DEFAULT_DEVICE_TYPES:
            if device_type not in existing_types:
                self.connection.execute(
                    "INSERT INTO device_types (name) VALUES (?)",
                    (device_type,),
                )
        self.connection.commit()

    def _apply_compat_migrations(self) -> None:
        movement_columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(movements)").fetchall()
        }
        if "quantity" not in movement_columns:
            self.connection.execute(
                "ALTER TABLE movements ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1"
            )

        item_columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(items)").fetchall()
        }
        if "current_location_id" in item_columns:
            self.connection.execute(
                """
                INSERT INTO item_stock (item_id, location_id, quantity)
                SELECT id, current_location_id, 1
                FROM items
                WHERE current_location_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM item_stock s
                    WHERE s.item_id = items.id AND s.location_id = items.current_location_id
                )
                """
            )

    def create_country(self, name: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO countries (name) VALUES (?)", (name,)
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_location(self, country_id: int, name: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO locations (country_id, name) VALUES (?, ?)",
            (country_id, name),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_item(self, serial: str | None, name: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO items (serial, name) VALUES (?, ?)",
            (serial, name),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_device_user(self, name: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO device_users (name) VALUES (?)",
            (name,),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_device_type(self, name: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO device_types (name) VALUES (?)",
            (name,),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_device(
        self,
        serial: str,
        name: str,
        device_type_id: int,
        status: str,
        location_id: int,
        user_id: int | None,
        note: str | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO devices (
                serial, name, device_type_id, status, user_id, location_id, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (serial, name, device_type_id, status, user_id, location_id, note),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def get_country(self, country_id: int):
        return self.connection.execute(
            "SELECT * FROM countries WHERE id = ?", (country_id,)
        ).fetchone()

    def get_location(self, location_id: int):
        return self.connection.execute(
            "SELECT * FROM locations WHERE id = ?", (location_id,)
        ).fetchone()

    def get_item(self, item_id: int):
        return self.connection.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()

    def get_item_by_serial(self, serial: str):
        return self.connection.execute(
            "SELECT * FROM items WHERE serial = ?", (serial,)
        ).fetchone()

    def get_device_user(self, user_id: int):
        return self.connection.execute(
            "SELECT * FROM device_users WHERE id = ?",
            (user_id,),
        ).fetchone()

    def get_device_type(self, type_id: int):
        return self.connection.execute(
            "SELECT * FROM device_types WHERE id = ?",
            (type_id,),
        ).fetchone()

    def get_device(self, device_id: int):
        return self.connection.execute(
            "SELECT * FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()

    def get_device_by_serial(self, serial: str):
        return self.connection.execute(
            "SELECT * FROM devices WHERE serial = ?",
            (serial,),
        ).fetchone()

    def get_stock(self, item_id: int, location_id: int) -> int:
        row = self.connection.execute(
            "SELECT quantity FROM item_stock WHERE item_id = ? AND location_id = ?",
            (item_id, location_id),
        ).fetchone()
        return int(row["quantity"]) if row else 0

    def set_stock(self, item_id: int, location_id: int, quantity: int) -> None:
        if quantity <= 0:
            self.connection.execute(
                "DELETE FROM item_stock WHERE item_id = ? AND location_id = ?",
                (item_id, location_id),
            )
            return
        self.connection.execute(
            """
            INSERT INTO item_stock (item_id, location_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(item_id, location_id)
            DO UPDATE SET quantity = excluded.quantity
            """,
            (item_id, location_id, quantity),
        )

    def add_movement(
        self,
        item_id: int,
        movement_type: str,
        quantity: int,
        from_location_id: int | None,
        to_location_id: int | None,
        note: str | None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO movements (item_id, movement_type, quantity, from_location_id, to_location_id, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item_id, movement_type, quantity, from_location_id, to_location_id, note),
        )
        return int(cursor.lastrowid)

    def list_countries(self):
        return self.connection.execute(
            "SELECT * FROM countries ORDER BY name"
        ).fetchall()

    def list_locations(self):
        return self.connection.execute(
            """
            SELECT locations.*, countries.name AS country_name
            FROM locations
            JOIN countries ON countries.id = locations.country_id
            ORDER BY countries.name, locations.name
            """
        ).fetchall()

    def list_items(self):
        return self.connection.execute(
            """
            SELECT items.id,
                   items.serial,
                   items.name,
                   COALESCE(SUM(item_stock.quantity), 0) AS total_quantity
            FROM items
            LEFT JOIN item_stock ON item_stock.item_id = items.id
            GROUP BY items.id, items.serial, items.name
            ORDER BY items.serial, items.name
            """
        ).fetchall()

    def list_device_users(self):
        return self.connection.execute(
            "SELECT * FROM device_users ORDER BY name"
        ).fetchall()

    def list_device_types(self):
        return self.connection.execute(
            "SELECT * FROM device_types ORDER BY name"
        ).fetchall()

    def list_devices(self):
        return self.connection.execute(
            """
            SELECT devices.*,
                   device_users.name AS user_name,
                   device_types.name AS device_type_name,
                   locations.name AS location_name,
                   countries.name AS country_name
            FROM devices
            LEFT JOIN device_users ON device_users.id = devices.user_id
            JOIN device_types ON device_types.id = devices.device_type_id
            JOIN locations ON locations.id = devices.location_id
            JOIN countries ON countries.id = locations.country_id
            ORDER BY devices.name, devices.serial
            """
        ).fetchall()

    def list_dashboard_devices(
        self,
        country_id: int | None = None,
        location_id: int | None = None,
        device_query: str | None = None,
    ):
        query = """
            SELECT devices.id AS device_id,
                   devices.serial,
                   devices.name AS device_name,
                   devices.status,
                   device_types.name AS device_type_name,
                   device_users.name AS user_name,
                   countries.id AS country_id,
                   countries.name AS country_name,
                   locations.id AS location_id,
                   locations.name AS location_name
            FROM devices
            JOIN device_types ON device_types.id = devices.device_type_id
            LEFT JOIN device_users ON device_users.id = devices.user_id
            JOIN locations ON locations.id = devices.location_id
            JOIN countries ON countries.id = locations.country_id
        """
        conditions = []
        params: list[int | str] = []
        if country_id is not None:
            conditions.append("countries.id = ?")
            params.append(country_id)
        if location_id is not None:
            conditions.append("locations.id = ?")
            params.append(location_id)
        if device_query:
            conditions.append(
                """
                (
                    LOWER(devices.name) LIKE ?
                    OR LOWER(COALESCE(devices.serial, '')) LIKE ?
                    OR LOWER(device_types.name) LIKE ?
                )
                """
            )
            search = f"%{device_query.lower()}%"
            params.extend((search, search, search))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += """
            ORDER BY countries.name,
                     locations.name,
                     device_types.name,
                     devices.name,
                     devices.serial
        """
        return self.connection.execute(query, tuple(params)).fetchall()

    def list_device_transfers(self):
        return self.connection.execute(
            """
            SELECT device_transfers.*,
                   devices.serial AS device_serial,
                   devices.name AS device_name,
                   device_types.name AS device_type_name,
                   from_user.name AS from_user_name,
                   to_user.name AS to_user_name,
                   from_location.name AS from_location_name,
                   to_location.name AS to_location_name
            FROM device_transfers
            JOIN devices ON devices.id = device_transfers.device_id
            JOIN device_types ON device_types.id = devices.device_type_id
            LEFT JOIN device_users AS from_user
                ON from_user.id = device_transfers.from_user_id
            LEFT JOIN device_users AS to_user
                ON to_user.id = device_transfers.to_user_id
            JOIN locations AS from_location
                ON from_location.id = device_transfers.from_location_id
            JOIN locations AS to_location
                ON to_location.id = device_transfers.to_location_id
            ORDER BY device_transfers.created_at DESC, device_transfers.id DESC
            """
        ).fetchall()

    def list_movements(self, item_id: int | None = None):
        query = """
            SELECT movements.*,
                   items.serial AS item_serial,
                   items.name AS item_name,
                   from_l.name AS from_location_name,
                   to_l.name AS to_location_name
            FROM movements
            JOIN items ON items.id = movements.item_id
            LEFT JOIN locations AS from_l ON from_l.id = movements.from_location_id
            LEFT JOIN locations AS to_l ON to_l.id = movements.to_location_id
        """
        params: tuple = ()
        if item_id is not None:
            query += " WHERE movements.item_id = ?"
            params = (item_id,)
        query += " ORDER BY movements.created_at DESC, movements.id DESC"
        return self.connection.execute(query, params).fetchall()

    def list_stock_for_item(self, item_id: int):
        return self.connection.execute(
            """
            SELECT item_stock.*,
                   locations.name AS location_name,
                   countries.name AS country_name
            FROM item_stock
            JOIN locations ON locations.id = item_stock.location_id
            JOIN countries ON countries.id = locations.country_id
            WHERE item_stock.item_id = ?
            ORDER BY countries.name, locations.name
            """,
            (item_id,),
        ).fetchall()

    def list_device_assignments(self, status: str | None = None):
        query = """
            SELECT devices.id,
                   devices.serial,
                   devices.name,
                   devices.status,
                   devices.user_id,
                   device_users.name AS user_name,
                   device_types.name AS device_type_name,
                   locations.name AS location_name,
                   countries.name AS country_name
            FROM devices
            LEFT JOIN device_users ON device_users.id = devices.user_id
            JOIN device_types ON device_types.id = devices.device_type_id
            JOIN locations ON locations.id = devices.location_id
            JOIN countries ON countries.id = locations.country_id
        """
        params: tuple = ()
        if status is not None:
            query += " WHERE devices.status = ?"
            params = (status,)
        query += " ORDER BY devices.name, devices.serial"
        return self.connection.execute(query, params).fetchall()

    def update_device(
        self,
        device_id: int,
        device_type_id: int,
        status: str,
        location_id: int,
        user_id: int | None,
        note: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE devices
            SET status = ?,
                device_type_id = ?,
                user_id = ?,
                location_id = ?,
                note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, device_type_id, user_id, location_id, note, device_id),
        )

    def add_device_transfer(
        self,
        device_id: int,
        from_user_id: int | None,
        to_user_id: int | None,
        from_location_id: int,
        to_location_id: int,
        from_status: str,
        to_status: str,
        note: str | None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO device_transfers (
                device_id,
                from_user_id,
                to_user_id,
                from_location_id,
                to_location_id,
                from_status,
                to_status,
                note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                from_user_id,
                to_user_id,
                from_location_id,
                to_location_id,
                from_status,
                to_status,
                note,
            ),
        )
        return int(cursor.lastrowid)

    def list_dashboard_stock(
        self,
        country_id: int | None = None,
        location_id: int | None = None,
        item_query: str | None = None,
    ):
        query = """
            SELECT items.id AS item_id,
                   items.serial,
                   items.name AS item_name,
                   countries.id AS country_id,
                   countries.name AS country_name,
                   locations.id AS location_id,
                   locations.name AS location_name,
                   item_stock.quantity
            FROM item_stock
            JOIN items ON items.id = item_stock.item_id
            JOIN locations ON locations.id = item_stock.location_id
            JOIN countries ON countries.id = locations.country_id
            WHERE item_stock.quantity > 0
        """
        conditions = []
        params: list[int | str] = []
        if country_id is not None:
            conditions.append("countries.id = ?")
            params.append(country_id)
        if location_id is not None:
            conditions.append("locations.id = ?")
            params.append(location_id)
        if item_query:
            conditions.append(
                "(LOWER(items.name) LIKE ? OR LOWER(COALESCE(items.serial, '')) LIKE ?)"
            )
            search = f"%{item_query.lower()}%"
            params.extend((search, search))
        if conditions:
            query += " AND " + " AND ".join(conditions)
        query += """
            ORDER BY countries.name,
                     locations.name,
                     items.name,
                     items.serial
        """
        return self.connection.execute(query, tuple(params)).fetchall()

    def count_items_at_location(self, location_id: int) -> int:
        row = self.connection.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS total FROM item_stock WHERE location_id = ?",
            (location_id,),
        ).fetchone()
        return int(row["total"])

    def count_items_with_location(self) -> int:
        row = self.connection.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS total FROM item_stock",
        ).fetchone()
        return int(row["total"])
