from __future__ import annotations

from typing import Any

from .crawler.crawler import CrawlError, SiteCrawler
from .crawler.models import CrawlRequest
from .dual_device_crawl import crawl_both_devices
from .history_orchestration import persist_crawl_result, persist_dual_crawl_result
from .history_store import HistoryStore
from .monitoring import MonitorStore, build_alerts, dedupe_alerts


async def execute_monitor(
    monitor_id: str,
    target: dict[str, Any],
    *,
    crawler: SiteCrawler,
    history_store: HistoryStore,
    monitor_store: MonitorStore,
) -> dict[str, Any]:
    """Execute one enabled monitor and persist its history/alerts."""
    if not target.get("enabled", True):
        raise ValueError("Monitor is disabled")

    url = str(target["target"])
    device = str(target.get("device", "desktop"))
    options = target.get("crawl_options") if isinstance(target.get("crawl_options"), dict) else {}
    request = CrawlRequest(
        url=url,
        trace=bool(options.get("trace", False)),
        enrich_landing_pages=bool(options.get("enrich_landing_pages", False)),
        max_landing_destinations=int(options.get("max_landing_destinations", 10)),
        device="desktop",
    )
    previous = history_store.load(url)

    if device == "both":
        crawl_result = await crawl_both_devices(crawler, request)
        stored = persist_dual_crawl_result(history_store, url, crawl_result)
    else:
        request = request.model_copy(update={"device": device})
        crawl_result = await crawler.crawl(request)
        stored = persist_crawl_result(history_store, url, crawl_result)

    current_session_id = stored["crawl_session_id"]
    current = [row for row in history_store.load(url) if row.get("crawl_session_id") == current_session_id]
    current_session_ids = {str(row.get("crawl_session_id")) for row in current}
    prior = [row for row in previous if str(row.get("crawl_session_id")) not in current_session_ids]
    if prior:
        prior_timestamp = max(str(row.get("observed_at") or "") for row in prior)
        prior = [row for row in prior if str(row.get("observed_at") or "") == prior_timestamp]

    candidates = build_alerts(
        monitor_id=monitor_id,
        target=url,
        previous=prior,
        current=current,
        observed_at=stored["observed_at"],
    )
    fresh = dedupe_alerts(monitor_store.alerts(monitor_id), candidates)
    monitor_store.append_alerts(fresh)
    return {"monitor_id": monitor_id, "crawl": crawl_result, "history": stored, "alerts": fresh}


__all__ = ["execute_monitor"]
