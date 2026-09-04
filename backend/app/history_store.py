from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .sqlite_store import SQLiteStore


def target_key(url: str) -> str:
    parsed = urlsplit(str(url).strip())
    origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}" if parsed.netloc else str(url).strip().lower()
    return hashlib.sha256(origin.encode("utf-8")).hexdigest()[:24]


class HistoryStore:
    """Transactional SQLite-backed history store with one-time legacy JSON import."""

    def __init__(self, root: str | Path = "data/history") -> None:
        self.root = Path(root)
        self._ensure_database()

    @property
    def db(self) -> SQLiteStore:
        return SQLiteStore(self.root / "history.sqlite3")

    def _ensure_database(self) -> None:
        db = self.db
        with db.transaction() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, target_key TEXT NOT NULL, observed_at TEXT,
                crawl_session_id TEXT, monitor_id TEXT, payload TEXT NOT NULL
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_observations_target_time ON observations(target_key, observed_at, id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_observations_session ON observations(crawl_session_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_observations_monitor ON observations(monitor_id)")
        self._migrate_legacy_json(db)

    def _migrate_legacy_json(self, db: SQLiteStore | None = None) -> None:
        db = db or self.db
        marker = self.root / ".sqlite_migrated"
        if marker.exists() or not self.root.is_dir():
            return
        for path in sorted(self.root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
                continue
            key = path.stem
            with db.transaction() as connection:
                if connection.execute("SELECT 1 FROM observations WHERE target_key=? LIMIT 1", (key,)).fetchone():
                    continue
                connection.executemany(
                    "INSERT INTO observations(target_key,observed_at,crawl_session_id,monitor_id,payload) VALUES(?,?,?,?,?)",
                    [(key, row.get("observed_at"), row.get("crawl_session_id"), row.get("monitor_id"), db.encode(row)) for row in payload],
                )
        try:
            marker.write_text("sqlite", encoding="utf-8")
        except OSError:
            pass

    def path_for(self, target: str) -> Path:
        return self.root / f"{target_key(target)}.json"

    def load(self, target: str) -> list[dict[str, Any]]:
        self._ensure_database()
        db = self.db
        with db.transaction() as connection:
            rows = connection.execute("SELECT payload FROM observations WHERE target_key=? ORDER BY id", (target_key(target),)).fetchall()
        result = []
        for row in rows:
            try:
                value = db.decode(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                result.append(value)
        return result

    def append(self, target: str, observations: list[dict[str, Any]]) -> dict[str, int | str]:
        if not all(isinstance(row, dict) for row in observations):
            raise ValueError("observations must be a list of objects")
        self._ensure_database()
        db = self.db
        key = target_key(target)
        with db.transaction() as connection:
            connection.executemany(
                "INSERT INTO observations(target_key,observed_at,crawl_session_id,monitor_id,payload) VALUES(?,?,?,?,?)",
                [(key, row.get("observed_at"), row.get("crawl_session_id"), row.get("monitor_id"), db.encode(row)) for row in observations],
            )
            count = int(connection.execute("SELECT COUNT(*) FROM observations WHERE target_key=?", (key,)).fetchone()[0])
        return {"target": key, "observations_added": len(observations), "history_size": count}

    def clear(self, target: str) -> None:
        self._ensure_database()
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM observations WHERE target_key=?", (target_key(target),))


__all__ = ["HistoryStore", "target_key"]
