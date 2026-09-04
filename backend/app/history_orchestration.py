from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .crawler.models import CrawlResult
from .history import build_snapshot
from .history_store import HistoryStore


def utc_timestamp() -> str:
    """Return a UTC timestamp with second precision for one monitoring session."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def persist_crawl_result(
    store: HistoryStore,
    target: str,
    result: CrawlResult,
    *,
    session_id: str | None = None,
    observed_at: str | None = None,
    monitor_id: str | None = None,
) -> dict[str, Any]:
    """Persist one crawl as a grouped historical observation."""
    session = session_id or uuid4().hex
    timestamp = observed_at or utc_timestamp()
    observations = build_snapshot(result.ad_records, timestamp)
    for row in observations:
        row["device"] = result.device
        row["crawl_session_id"] = session
        row["run_id"] = result.run_id
        row["target_url"] = target
        if monitor_id:
            row["monitor_id"] = monitor_id
    stored = store.append(target, observations)
    return {
        **stored,
        "crawl_session_id": session,
        "observed_at": timestamp,
        "run_id": result.run_id,
        "device": result.device,
        "monitor_id": monitor_id,
    }


def persist_dual_crawl_result(
    store: HistoryStore,
    target: str,
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
    observed_at: str | None = None,
    monitor_id: str | None = None,
) -> dict[str, Any]:
    """Persist desktop/mobile crawl output under one shared monitoring session."""
    session = session_id or uuid4().hex
    timestamp = observed_at or utc_timestamp()
    observations: list[dict[str, Any]] = []
    for device in ("desktop", "mobile"):
        raw = payload.get(device)
        if not isinstance(raw, dict):
            continue
        result = CrawlResult.model_validate(raw)
        for row in build_snapshot(result.ad_records, timestamp):
            row["device"] = device
            row["crawl_session_id"] = session
            row["run_id"] = result.run_id
            row["target_url"] = target
            if monitor_id:
                row["monitor_id"] = monitor_id
            observations.append(row)
    stored = store.append(target, observations)
    return {
        **stored,
        "crawl_session_id": session,
        "observed_at": timestamp,
        "devices": ["desktop", "mobile"],
        "monitor_id": monitor_id,
    }


__all__ = ["persist_crawl_result", "persist_dual_crawl_result", "utc_timestamp"]
