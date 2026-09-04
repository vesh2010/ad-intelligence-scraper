from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .device_change import detect_changes
from .history_store import target_key


class MonitorStore:
    """JSON-backed monitoring target and alert store for single-instance deployments."""

    def __init__(self, root: str | Path = "data/monitoring") -> None:
        self.root = Path(root)

    @property
    def path(self) -> Path:
        return self.root / "targets.json"

    @property
    def alerts_path(self) -> Path:
        return self.root / "alerts.json"

    def _load(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [x for x in payload if isinstance(x, dict)] if isinstance(payload, list) else []

    def _save(self, path: Path, rows: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def list_targets(self) -> list[dict[str, Any]]:
        return self._load(self.path)

    def get(self, monitor_id: str) -> dict[str, Any] | None:
        return next((x for x in self.list_targets() if x.get("monitor_id") == monitor_id), None)

    def upsert(self, target: dict[str, Any]) -> dict[str, Any]:
        rows = [x for x in self.list_targets() if x.get("monitor_id") != target["monitor_id"]]
        rows.append(dict(target))
        self._save(self.path, rows)
        return target

    def delete(self, monitor_id: str) -> bool:
        rows = self.list_targets()
        kept = [x for x in rows if x.get("monitor_id") != monitor_id]
        if len(kept) == len(rows):
            return False
        self._save(self.path, kept)
        return True

    def alerts(self, monitor_id: str | None = None) -> list[dict[str, Any]]:
        rows = self._load(self.alerts_path)
        return [x for x in rows if x.get("monitor_id") == monitor_id] if monitor_id else rows

    def append_alerts(self, alerts: list[dict[str, Any]]) -> None:
        if alerts:
            rows = self.alerts()
            rows.extend(dict(x) for x in alerts)
            self._save(self.alerts_path, rows)


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
    """Turn evidence-backed changes into alert records; continued/no-op campaigns are omitted."""
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