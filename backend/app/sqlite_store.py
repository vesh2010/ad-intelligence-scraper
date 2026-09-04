from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator


class SQLiteStore:
    """Small transactional SQLite helper with WAL and bounded lock waiting."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    @staticmethod
    def encode(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def decode(value: str) -> Any:
        return json.loads(value)

    def transaction(self) -> sqlite3.Connection:
        return self.connect()


__all__ = ["SQLiteStore"]
