from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .database import open_database_connection
from .domain import DatabaseOpenError


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
        self.connection.executescript("""
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
            """)
        self._apply_compat_migrations()
        self.connection.commit()

    def _apply_compat_migrations(self) -> None:
        movement_columns = {
            row["name"]
            for row in self.connection.execute(
                "PRAGMA table_info(movements)"
            ).fetchall()
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
            self.connection.execute("""
                INSERT INTO item_stock (item_id, location_id, quantity)
                SELECT id, current_location_id, 1
                FROM items
                WHERE current_location_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM item_stock s
                    WHERE s.item_id = items.id AND s.location_id = items.current_location_id
                )
                """)

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
        return self.connection.execute("""
            SELECT locations.*, countries.name AS country_name
            FROM locations
            JOIN countries ON countries.id = locations.country_id
            ORDER BY countries.name, locations.name
            """).fetchall()

    def list_items(self):
        return self.connection.execute("""
            SELECT items.id,
                   items.serial,
                   items.name,
                   COALESCE(SUM(item_stock.quantity), 0) AS total_quantity
            FROM items
            LEFT JOIN item_stock ON item_stock.item_id = items.id
            GROUP BY items.id, items.serial, items.name
            ORDER BY items.serial, items.name
            """).fetchall()

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
