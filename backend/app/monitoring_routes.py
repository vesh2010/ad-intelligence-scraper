from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .crawler.crawler import CrawlError, SiteCrawler
from .history_store import HistoryStore
from .monitor_execution import execute_monitor
from .monitor_scheduler import next_run_at
from .monitoring import MonitorStore, create_monitor_target


def _with_schedule(target: dict[str, Any]) -> dict[str, Any]:
    result = dict(target)
    result["next_run_at"] = next_run_at(result)
    return result


def build_monitor_router(
    first: SiteCrawler | MonitorStore,
    second: HistoryStore | SiteCrawler,
    third: MonitorStore | HistoryStore,
) -> APIRouter:
    """Build the monitoring router while accepting both historical argument orders.

    The canonical order is ``crawler, history_store, monitor_store``.  The
    compatibility branch also accepts ``monitor_store, crawler, history_store``
    used by the application wiring in older revisions.
    """
    if isinstance(first, MonitorStore):
        monitor_store = first
        crawler = second
        history_store = third
    else:
        crawler = first
        history_store = second
        monitor_store = third

    if not isinstance(crawler, SiteCrawler) or not isinstance(history_store, HistoryStore) or not isinstance(monitor_store, MonitorStore):
        raise TypeError("build_monitor_router received invalid store/crawler arguments")

    router = APIRouter(prefix="/api/monitors", tags=["monitoring"])

    @router.get("")
    async def list_monitors() -> dict[str, Any]:
        targets = [_with_schedule(target) for target in monitor_store.list_targets()]
        return {"monitors": targets, "count": len(targets)}

    @router.post("")
    async def create_monitor(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            target = create_monitor_target(
                url=str(payload.get("url") or ""), device=str(payload.get("device") or "desktop"),
                enabled=bool(payload.get("enabled", True)), interval_minutes=int(payload.get("interval_minutes", 60)),
                trace=bool(payload.get("trace", False)), enrich_landing_pages=bool(payload.get("enrich_landing_pages", False)),
                max_landing_destinations=int(payload.get("max_landing_destinations", 10)),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        monitor_store.upsert(target)
        return _with_schedule(target)

    @router.get("/{monitor_id}")
    async def get_monitor(monitor_id: str) -> dict[str, Any]:
        target = monitor_store.get(monitor_id)
        if not target:
            raise HTTPException(status_code=404, detail="Monitor not found")
        return _with_schedule(target)

    @router.patch("/{monitor_id}")
    async def update_monitor(monitor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        target = monitor_store.get(monitor_id)
        if not target:
            raise HTTPException(status_code=404, detail="Monitor not found")
        if "enabled" in payload:
            target["enabled"] = bool(payload["enabled"])
        if "interval_minutes" in payload:
            try:
                interval = int(payload["interval_minutes"])
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail="interval_minutes must be an integer") from exc
            if interval < 60:
                raise HTTPException(status_code=422, detail="interval_minutes must be at least 60")
            target["interval_minutes"] = interval
        if "device" in payload:
            if payload["device"] not in {"desktop", "mobile", "both"}:
                raise HTTPException(status_code=422, detail="device must be desktop, mobile, or both")
            target["device"] = payload["device"]
        monitor_store.upsert(target)
        return _with_schedule(target)

    @router.delete("/{monitor_id}")
    async def delete_monitor(monitor_id: str) -> dict[str, Any]:
        if not monitor_store.delete(monitor_id):
            raise HTTPException(status_code=404, detail="Monitor not found")
        return {"deleted": True, "monitor_id": monitor_id}

    @router.get("/{monitor_id}/alerts")
    async def get_alerts(monitor_id: str) -> dict[str, Any]:
        if not monitor_store.get(monitor_id):
            raise HTTPException(status_code=404, detail="Monitor not found")
        alerts = monitor_store.alerts(monitor_id)
        return {"alerts": alerts, "count": len(alerts)}

    @router.post("/{monitor_id}/run")
    async def run_monitor(monitor_id: str) -> dict[str, Any]:
        target = monitor_store.get(monitor_id)
        if not target:
            raise HTTPException(status_code=404, detail="Monitor not found")
        if not target.get("enabled", True):
            raise HTTPException(status_code=409, detail="Monitor is disabled")
        try:
            return await execute_monitor(monitor_id, target, crawler=crawler, history_store=history_store, monitor_store=monitor_store)
        except CrawlError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Monitoring run failed: {exc}") from exc

    return router
