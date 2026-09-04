from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .crawler.crawler import CrawlError, SiteCrawler
from .crawler.models import CrawlRequest
from .dual_device_crawl import crawl_both_devices
from .history_orchestration import persist_crawl_result, persist_dual_crawl_result
from .history_store import HistoryStore
from .monitoring import MonitorStore, build_alerts, create_monitor_target, dedupe_alerts


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
        url = str(target["target"])
        device = str(target.get("device", "desktop"))
        options = target.get("crawl_options") if isinstance(target.get("crawl_options"), dict) else {}
        request = CrawlRequest(url=url, trace=bool(options.get("trace", False)), enrich_landing_pages=bool(options.get("enrich_landing_pages", False)), max_landing_destinations=int(options.get("max_landing_destinations", 10)), device="desktop")
        previous = history_store.load(url)
        try:
            if device == "both":
                crawl_result = await crawl_both_devices(crawler, request)
                stored = persist_dual_crawl_result(history_store, url, crawl_result)
            else:
                request = request.model_copy(update={"device": device})
                crawl_result = await crawler.crawl(request)
                stored = persist_crawl_result(history_store, url, crawl_result)
        except CrawlError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Monitoring run failed: {exc}") from exc
        current = [row for row in history_store.load(url) if row.get("crawl_session_id") == stored["crawl_session_id"]]
        previous_sessions = {str(row.get("crawl_session_id")) for row in current}
        prior = [row for row in previous if str(row.get("crawl_session_id")) not in previous_sessions]
        if prior:
            prior_timestamp = max(str(row.get("observed_at") or "") for row in prior)
            prior = [row for row in prior if str(row.get("observed_at") or "") == prior_timestamp]
        candidates = build_alerts(monitor_id=monitor_id, target=url, previous=prior, current=current, observed_at=stored["observed_at"])
        fresh = dedupe_alerts(monitor_store.alerts(monitor_id), candidates)
        monitor_store.append_alerts(fresh)
        return {"monitor_id": monitor_id, "crawl": crawl_result, "history": stored, "alerts": fresh}

    return router
