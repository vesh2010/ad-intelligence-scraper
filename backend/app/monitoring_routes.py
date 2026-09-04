from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .crawler.crawler import CrawlError, SiteCrawler
from .monitor_execution import execute_monitor
from .monitoring import MonitorStore, create_monitor_target
from .history_store import HistoryStore


def build_monitor_router(crawler: SiteCrawler, history_store: HistoryStore, monitor_store: MonitorStore) -> APIRouter:
    router = APIRouter(prefix="/api/monitors", tags=["monitoring"])

    @router.get("")
    async def list_monitors() -> dict[str, Any]:
        targets = monitor_store.list_targets()
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
        return target

    @router.get("/{monitor_id}")
    async def get_monitor(monitor_id: str) -> dict[str, Any]:
        target = monitor_store.get(monitor_id)
        if not target:
            raise HTTPException(status_code=404, detail="Monitor not found")
        return target

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
        return target

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
            return await execute_monitor(
                monitor_id,
                target,
                crawler=crawler,
                history_store=history_store,
                monitor_store=monitor_store,
            )
        except CrawlError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Monitoring run failed: {exc}") from exc

    return router
