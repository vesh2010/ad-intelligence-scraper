from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .device_change import detect_changes
from .history_store import target_key
from .sqlite_store import SQLiteStore


class MonitorStore:
    """Transactional SQLite-backed monitoring target and alert store."""

    def __init__(self, root: str | Path = "data/monitoring") -> None:
        self.root = Path(root)
        self.db = SQLiteStore(self.root / "monitoring.sqlite3")
        self._initialize()
        self._migrate_legacy_json()

    @property
    def path(self) -> Path:
        return self.root / "targets.json"

    @property
    def alerts_path(self) -> Path:
        return self.root / "alerts.json"

    def _initialize(self) -> None:
        with self.db.transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS monitors (
                monitor_id TEXT PRIMARY KEY, target TEXT NOT NULL, target_key TEXT NOT NULL,
                device TEXT NOT NULL, enabled INTEGER NOT NULL, interval_minutes INTEGER NOT NULL,
                crawl_options TEXT NOT NULL, created_at TEXT, updated_at TEXT,
                last_run_at TEXT, last_run_status TEXT, last_error TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_monitors_target_key ON monitors(target_key)")
            db.execute("""CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, target TEXT NOT NULL,
                observed_at TEXT, severity TEXT NOT NULL, change_type TEXT NOT NULL,
                campaign_key TEXT, details TEXT NOT NULL,
                FOREIGN KEY(monitor_id) REFERENCES monitors(monitor_id) ON DELETE CASCADE
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_monitor_time ON alerts(monitor_id, observed_at, alert_id)")

    def _migrate_legacy_json(self) -> None:
        marker = self.root / ".sqlite_migrated"
        if marker.exists() or not self.root.is_dir():
            return
        targets: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else []
            targets = [x for x in payload if isinstance(x, dict)] if isinstance(payload, list) else []
        except (OSError, json.JSONDecodeError):
            pass
        try:
            payload = json.loads(self.alerts_path.read_text(encoding="utf-8")) if self.alerts_path.is_file() else []
            alerts = [x for x in payload if isinstance(x, dict)] if isinstance(payload, list) else []
        except (OSError, json.JSONDecodeError):
            pass
        with self.db.transaction() as db:
            for row in targets:
                db.execute("""INSERT OR IGNORE INTO monitors
                    (monitor_id,target,target_key,device,enabled,interval_minutes,crawl_options,created_at,updated_at,last_run_at,last_run_status,last_error)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row.get("monitor_id"), row.get("target", ""), row.get("target_key", target_key(str(row.get("target", "")))),
                     row.get("device", "desktop"), int(bool(row.get("enabled", True))), int(row.get("interval_minutes", 60)),
                     self.db.encode(row.get("crawl_options", {})), row.get("created_at"), row.get("updated_at"), row.get("last_run_at"),
                     row.get("last_run_status"), row.get("last_error")))
            for row in alerts:
                monitor_id = str(row.get("monitor_id", ""))
                if not db.execute("SELECT 1 FROM monitors WHERE monitor_id=?", (monitor_id,)).fetchone():
                    continue
                db.execute("""INSERT OR IGNORE INTO alerts
                    (alert_id,monitor_id,target,observed_at,severity,change_type,campaign_key,details)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (row.get("alert_id", uuid4().hex), monitor_id, row.get("target", ""), row.get("observed_at"),
                     row.get("severity", "medium"), row.get("change_type", "change"), row.get("campaign_key"), self.db.encode(row.get("details", {}))))
        try:
            marker.write_text("sqlite", encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["enabled"] = bool(result.get("enabled"))
        try:
            result["crawl_options"] = json.loads(result.get("crawl_options") or "{}")
        except json.JSONDecodeError:
            result["crawl_options"] = {}
        for key in ("last_run_at", "last_run_status", "last_error"):
            if result.get(key) is None:
                result.pop(key, None)
        return result

    def list_targets(self) -> list[dict[str, Any]]:
        with self.db.transaction() as db:
            rows = db.execute("SELECT * FROM monitors ORDER BY created_at, monitor_id").fetchall()
        return [self._row(row) for row in rows]

    def get(self, monitor_id: str) -> dict[str, Any] | None:
        with self.db.transaction() as db:
            row = db.execute("SELECT * FROM monitors WHERE monitor_id=?", (monitor_id,)).fetchone()
        return self._row(row) if row else None

    def upsert(self, target: dict[str, Any]) -> dict[str, Any]:
        fields = (target["monitor_id"], target["target"], target["target_key"], target["device"], int(bool(target["enabled"])),
                  int(target["interval_minutes"]), self.db.encode(target.get("crawl_options", {})), target.get("created_at"), target.get("updated_at"),
                  target.get("last_run_at"), target.get("last_run_status"), target.get("last_error"))
        with self.db.transaction() as db:
            db.execute("""INSERT INTO monitors
                (monitor_id,target,target_key,device,enabled,interval_minutes,crawl_options,created_at,updated_at,last_run_at,last_run_status,last_error)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(monitor_id) DO UPDATE SET target=excluded.target,target_key=excluded.target_key,device=excluded.device,
                enabled=excluded.enabled,interval_minutes=excluded.interval_minutes,crawl_options=excluded.crawl_options,
                created_at=excluded.created_at,updated_at=excluded.updated_at,last_run_at=excluded.last_run_at,
                last_run_status=excluded.last_run_status,last_error=excluded.last_error""", fields)
        return dict(target)

    def delete(self, monitor_id: str) -> bool:
        with self.db.transaction() as db:
            cursor = db.execute("DELETE FROM monitors WHERE monitor_id=?", (monitor_id,))
        return cursor.rowcount > 0

    def alerts(self, monitor_id: str | None = None) -> list[dict[str, Any]]:
        with self.db.transaction() as db:
            rows = db.execute("SELECT * FROM alerts WHERE monitor_id=? ORDER BY observed_at, alert_id", (monitor_id,)).fetchall() if monitor_id else db.execute("SELECT * FROM alerts ORDER BY observed_at, alert_id").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item.get("details") or "{}")
            except json.JSONDecodeError:
                item["details"] = {}
            result.append(item)
        return result

    def append_alerts(self, alerts: list[dict[str, Any]]) -> None:
        if not alerts:
            return
        with self.db.transaction() as db:
            db.executemany("""INSERT OR IGNORE INTO alerts
                (alert_id,monitor_id,target,observed_at,severity,change_type,campaign_key,details)
                VALUES(?,?,?,?,?,?,?,?)""",
                [(x.get("alert_id", uuid4().hex), x.get("monitor_id", ""), x.get("target", ""), x.get("observed_at"),
                  x.get("severity", "medium"), x.get("change_type", "change"), x.get("campaign_key"), self.db.encode(x.get("details", {}))) for x in alerts])


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_monitor_target(*, url: str, device: str = "desktop", enabled: bool = True, interval_minutes: int = 60, **options: Any) -> dict[str, Any]:
    if not str(url).strip().lower().startswith(("http://", "https://")):
        raise ValueError("url must use http or https")
    if device not in {"desktop", "mobile", "both"}:
        raise ValueError("device must be desktop, mobile, or both")
    if interval_minutes < 60:
        raise ValueError("interval_minutes must be at least 60")
    now = utc_timestamp()
    return {"monitor_id": uuid4().hex, "target": str(url).strip(), "target_key": target_key(url), "device": device,
            "enabled": bool(enabled), "interval_minutes": int(interval_minutes), "crawl_options": dict(options),
            "created_at": now, "updated_at": now}


def build_alerts(*, monitor_id: str, target: str, previous: list[dict[str, Any]], current: list[dict[str, Any]], observed_at: str | None = None) -> list[dict[str, Any]]:
    changes = detect_changes(previous, current)["changes"]
    timestamp = observed_at or utc_timestamp()
    alerts: list[dict[str, Any]] = []
    for change in changes:
        change_type = str(change.get("change") or "change")
        if change_type == "continued":
            continue
        severity = "high" if change_type in {"new_campaign", "campaign_disappeared", "device_targeting_changed"} else "medium"
        alerts.append({"alert_id": uuid4().hex, "monitor_id": monitor_id, "target": target, "observed_at": timestamp,
                       "severity": severity, "change_type": change_type,
                       "campaign_key": change.get("campaign_key") or change.get("ad_id"), "details": change})
    return alerts


def dedupe_alerts(existing: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = {(x.get("monitor_id"), x.get("campaign_key"), x.get("change_type"), json.dumps(x.get("details", {}), sort_keys=True)) for x in existing}
    result: list[dict[str, Any]] = []
    for alert in candidates:
        key = (alert.get("monitor_id"), alert.get("campaign_key"), alert.get("change_type"), json.dumps(alert.get("details", {}), sort_keys=True))
        if key not in keys:
            result.append(alert)
            keys.add(key)
    return result


__all__ = ["MonitorStore", "create_monitor_target", "build_alerts", "dedupe_alerts", "utc_timestamp"]
