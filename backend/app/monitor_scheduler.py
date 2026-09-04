from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from .monitoring import MonitorStore

MIN_INTERVAL_MINUTES = 60


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _interval_minutes(target: dict[str, Any]) -> int:
    try:
        value = int(target.get("interval_minutes", MIN_INTERVAL_MINUTES))
    except (TypeError, ValueError, OverflowError):
        value = MIN_INTERVAL_MINUTES
    return max(MIN_INTERVAL_MINUTES, value)


def _utc_now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_due(target: dict[str, Any], *, now: datetime) -> bool:
    if not target.get("enabled", True):
        return False
    last_run = parse_timestamp(target.get("last_run_at"))
    if last_run is None:
        return True
    current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc) >= last_run + timedelta(minutes=_interval_minutes(target))


def next_run_at(target: dict[str, Any], *, now: datetime | None = None) -> str | None:
    """Return the next scheduled UTC run, or None when disabled/unscheduled."""
    if not target.get("enabled", True):
        return None
    last_run = parse_timestamp(target.get("last_run_at"))
    if last_run is None:
        return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if (now or datetime.now(timezone.utc)) else None
    return (last_run + timedelta(minutes=_interval_minutes(target))).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MonitorScheduler:
    """Small asyncio scheduler for single-instance deployments."""

    def __init__(self, store: MonitorStore, runner: Callable[[dict[str, Any]], Awaitable[Any]], *, clock: Callable[[], datetime] | None = None) -> None:
        self.store = store
        self.runner = runner
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._running: set[str] = set()

    def due_targets(self) -> list[dict[str, Any]]:
        now = _utc_now(self.clock)
        return [target for target in self.store.list_targets() if is_due(target, now=now) and target.get("monitor_id") not in self._running]

    async def run_due_once(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for target in self.due_targets():
            monitor_id = str(target.get("monitor_id"))
            self._running.add(monitor_id)
            try:
                result = await self.runner(target)
                target["last_run_at"] = _utc_now(self.clock).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                target["last_run_status"] = "success"
                target["last_error"] = None
                self.store.upsert(target)
                results.append({"monitor_id": monitor_id, "status": "success", "result": result})
            except Exception as exc:
                target["last_run_at"] = _utc_now(self.clock).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                target["last_run_status"] = "error"
                target["last_error"] = str(exc)
                self.store.upsert(target)
                results.append({"monitor_id": monitor_id, "status": "error", "error": str(exc)})
            finally:
                self._running.discard(monitor_id)
        return results

    async def start(self, *, poll_seconds: int = 60, stop_event: asyncio.Event | None = None) -> None:
        if poll_seconds < 1:
            raise ValueError("poll_seconds must be at least 1")
        stop = stop_event or asyncio.Event()
        while not stop.is_set():
            await self.run_due_once()
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                pass


__all__ = ["MonitorScheduler", "is_due", "parse_timestamp", "next_run_at", "MIN_INTERVAL_MINUTES"]
