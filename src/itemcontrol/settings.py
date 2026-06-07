from __future__ import annotations

import json
import os
from pathlib import Path


APP_DIR_NAME = "itemControl"
SETTINGS_FILE_NAME = "settings.json"


def settings_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        base_dir = Path(appdata)
    else:
        base_dir = Path.home() / ".config"
    return base_dir / APP_DIR_NAME / SETTINGS_FILE_NAME


def load_recent_databases(path: str | Path | None = None) -> list[str]:
    config_path = Path(path) if path is not None else settings_path()
    if not config_path.exists():
        return []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    recent = data.get("recent_databases", [])
    if not isinstance(recent, list):
        return []
    return [str(item) for item in recent if isinstance(item, str)]


def save_recent_databases(
    databases: list[str],
    path: str | Path | None = None,
) -> None:
    config_path = Path(path) if path is not None else settings_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    unique_databases = list(dict.fromkeys(databases))
    config_path.write_text(
        json.dumps({"recent_databases": unique_databases}, indent=2),
        encoding="utf-8",
    )


def add_recent_database(
    database_path: str | Path,
    path: str | Path | None = None,
    limit: int = 10,
) -> list[str]:
    resolved = str(Path(database_path).resolve())
    recent = load_recent_databases(path)
    updated = [resolved, *[item for item in recent if item != resolved]][:limit]
    save_recent_databases(updated, path)
    return updated
