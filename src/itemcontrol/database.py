from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .domain import DatabaseOpenError, ValidationError


def _load_sqlcipher() -> Any:
    try:
        from sqlcipher3 import dbapi2 as sqlcipher
    except ImportError as exc:
        raise DatabaseOpenError(
            "SQLCipher is required to open or create password-protected databases."
        ) from exc
    return sqlcipher


def _quote_sql_literal(value: str | Path) -> str:
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def open_database_connection(
    database_path: str | Path,
    password: str | None = None,
) -> sqlite3.Connection:
    path = Path(database_path)
    clean_password = password or None
    if clean_password is None:
        return sqlite3.connect(path)

    sqlcipher = _load_sqlcipher()
    connection = sqlcipher.connect(path)
    try:
        connection.execute(f"PRAGMA key = {_quote_sql_literal(clean_password)}")
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except Exception as exc:
        connection.close()
        raise DatabaseOpenError(
            "Could not unlock database. Check the password or choose an unencrypted database."
        ) from exc
    return connection


def encrypt_plaintext_database(
    source_path: str | Path,
    target_path: str | Path,
    password: str,
) -> None:
    source = Path(source_path)
    target = Path(target_path)
    clean_password = password.strip()
    if not clean_password:
        raise ValidationError("Password is required to protect a database.")
    if not source.exists():
        raise DatabaseOpenError("Source database was not found.")
    if target.exists():
        raise ValidationError("Destination database already exists.")

    sqlcipher = _load_sqlcipher()
    connection = sqlcipher.connect(source)
    try:
        connection.execute(
            f"ATTACH DATABASE {_quote_sql_literal(target)} AS encrypted "
            f"KEY {_quote_sql_literal(clean_password)}"
        )
        connection.execute("SELECT sqlcipher_export('encrypted')")
        connection.execute("DETACH DATABASE encrypted")
        connection.commit()
    except Exception as exc:
        connection.rollback()
        if target.exists():
            target.unlink()
        raise DatabaseOpenError("Could not create encrypted database copy.") from exc
    finally:
        connection.close()

    verify_connection = open_database_connection(target, clean_password)
    verify_connection.close()
