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
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def is_due(target: dict[str, Any], *, now: datetime) -> bool:
    if not target.get("enabled", True):
        return False
    interval = max(MIN_INTERVAL_MINUTES, int(target.get("interval_minutes", MIN_INTERVAL_MINUTES)))
    last_run = parse_timestamp(target.get("last_run_at"))
    if last_run is None:
        return True
    return now >= last_run + timedelta(minutes=interval)


class MonitorScheduler:
    """Small asyncio scheduler for single-instance deployments.

    The scheduler only decides when a monitor is due. The supplied runner owns
    the actual crawl and persistence work, making it deterministic and easy to
    test without starting Playwright.
    """

    def __init__(self, store: MonitorStore, runner: Callable[[dict[str, Any]], Awaitable[Any]], *, clock: Callable[[], datetime] | None = None) -> None:
        self.store = store
        self.runner = runner
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._running: set[str] = set()

    def due_targets(self) -> list[dict[str, Any]]:
        now = self.clock()
        return [target for target in self.store.list_targets() if is_due(target, now=now) and target.get("monitor_id") not in self._running]

    async def run_due_once(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for target in self.due_targets():
            monitor_id = str(target.get("monitor_id"))
            self._running.add(monitor_id)
            try:
                result = await self.runner(target)
                target["last_run_at"] = self.clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")
                target["last_run_status"] = "success"
                target["last_error"] = None
                self.store.upsert(target)
                results.append({"monitor_id": monitor_id, "status": "success", "result": result})
            except Exception as exc:
                target["last_run_at"] = self.clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")
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


__all__ = ["MonitorScheduler", "is_due", "parse_timestamp", "MIN_INTERVAL_MINUTES"]
