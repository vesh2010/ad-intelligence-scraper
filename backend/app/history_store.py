from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .sqlite_store import SQLiteStore


def target_key(url: str) -> str:
    """Return a stable key for a monitored site origin."""
    parsed = urlsplit(str(url).strip())
    origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}" if parsed.netloc else str(url).strip().lower()
    return hashlib.sha256(origin.encode("utf-8")).hexdigest()[:24]


class HistoryStore:
    """Transactional SQLite-backed history store with one-time legacy JSON import."""

    def __init__(self, root: str | Path = "data/history") -> None:
        self.root = Path(root)
        self.db = SQLiteStore(self.root / "history.sqlite3")
        self._initialize()
        self._migrate_legacy_json()

    def path_for(self, target: str) -> Path:
        """Legacy path retained for compatibility; new writes use SQLite."""
        return self.root / f"{target_key(target)}.json"

    def _initialize(self) -> None:
        with self.db.transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_key TEXT NOT NULL,
                observed_at TEXT,
                crawl_session_id TEXT,
                monitor_id TEXT,
                payload TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_observations_target_time ON observations(target_key, observed_at, id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_observations_session ON observations(crawl_session_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_observations_monitor ON observations(monitor_id)")

    def _migrate_legacy_json(self) -> None:
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
            with self.db.transaction() as db:
                exists = db.execute("SELECT 1 FROM observations WHERE target_key=? LIMIT 1", (key,)).fetchone()
                if exists:
                    continue
                db.executemany(
                    "INSERT INTO observations(target_key, observed_at, crawl_session_id, monitor_id, payload) VALUES(?,?,?,?,?)",
                    [(key, row.get("observed_at"), row.get("crawl_session_id"), row.get("monitor_id"), self.db.encode(row)) for row in payload],
                )
        try:
            marker.write_text("sqlite", encoding="utf-8")
        except OSError:
            pass

    def load(self, target: str) -> list[dict[str, Any]]:
        key = target_key(target)
        with self.db.transaction() as db:
            rows = db.execute("SELECT payload FROM observations WHERE target_key=? ORDER BY id", (key,)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                value = self.db.decode(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                result.append(value)
        return result

    def append(self, target: str, observations: list[dict[str, Any]]) -> dict[str, int | str]:
        if not all(isinstance(row, dict) for row in observations):
            raise ValueError("observations must be a list of objects")
        key = target_key(target)
        with self.db.transaction() as db:
            db.executemany(
                "INSERT INTO observations(target_key, observed_at, crawl_session_id, monitor_id, payload) VALUES(?,?,?,?,?)",
                [(key, row.get("observed_at"), row.get("crawl_session_id"), row.get("monitor_id"), self.db.encode(row)) for row in observations],
            )
            count = int(db.execute("SELECT COUNT(*) FROM observations WHERE target_key=?", (key,)).fetchone()[0])
        return {"target": key, "observations_added": len(observations), "history_size": count}

    def clear(self, target: str) -> None:
        with self.db.transaction() as db:
            db.execute("DELETE FROM observations WHERE target_key=?", (target_key(target),))


__all__ = ["HistoryStore", "target_key"]
