from __future__ import annotations

import asyncio
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from .crawler.crawler import CrawlError, SiteCrawler
from .crawler.models import CrawlRequest, CrawlResult, SiteCrawlRequest, SiteCrawlResult
from .device_change import detect_history_changes
from .dual_device_crawl import crawl_both_devices
from .history_orchestration import persist_crawl_result, persist_dual_crawl_result
from .history_store import HistoryStore
from .monitor_execution import execute_monitor
from .monitor_scheduler import MonitorScheduler
from .monitoring import MonitorStore
from .monitoring_routes import build_monitor_router
from .report_html import render_html_report
from .report_intelligence import build_report_intelligence
from .report_pdf import render_pdf_report
from .run_reports import build_run_report_router
from .site_crawl import crawl_site

crawler = SiteCrawler()
history_store = HistoryStore()
monitor_store = MonitorStore()
_scheduler_task: asyncio.Task[None] | None = None


def _scheduler_enabled() -> bool:
    return os.getenv("AD_SCRAPER_ENABLE_MONITOR_SCHEDULER", "0").strip().lower() in {"1", "true", "yes", "on"}


def _scheduler_poll_seconds() -> int:
    raw = os.getenv("AD_SCRAPER_MONITOR_POLL_SECONDS", "60")
    try:
        value = int(raw)
    except ValueError:
        return 60
    return max(1, value)


async def _run_monitor(target: dict[str, object]) -> dict[str, object]:
    return await execute_monitor(
        str(target.get("monitor_id")),
        target,
        crawler=crawler,
        history_store=history_store,
        monitor_store=monitor_store,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _scheduler_task
    if _scheduler_enabled():
        scheduler = MonitorScheduler(monitor_store, _run_monitor)
        _scheduler_task = asyncio.create_task(
            scheduler.start(poll_seconds=_scheduler_poll_seconds()),
            name="ad-intelligence-monitor-scheduler",
        )
    try:
        yield
    finally:
        if _scheduler_task is not None:
            _scheduler_task.cancel()
            try:
                await _scheduler_task
            except asyncio.CancelledError:
                pass
            _scheduler_task = None


app = FastAPI(title="Ad Intelligence Scraper", version="0.9.0", lifespan=lifespan)
app.include_router(build_monitor_router(crawler, history_store, monitor_store))
app.include_router(build_run_report_router(crawler.data_root))
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SAFE_IMAGE_RE = re.compile(r"^ad_candidates/[A-Za-z0-9_.-]+\.(?:png|jpe?g|webp)$")
ARTIFACTS = {
    "html": "page.html", "screenshot": "screenshot.png", "network": "network.json",
    "ads": "ads.json", "runtime_ads": "runtime_ads.json", "visual_evidence": "visual_evidence.json",
    "creative_assets": "creative_assets.json", "ad_records": "ad_records.json",
    "ad_request_resolution": "ad_request_resolution.json", "ads_txt": "ads.txt.json",
    "landing_enrichment": "landing_enrichment.json", "trace": "trace.zip",
}


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/crawl", response_model=CrawlResult)
async def crawl(request: CrawlRequest) -> CrawlResult:
    try:
        return await crawler.crawl(request)
    except CrawlError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {exc}") from exc


@app.post("/api/crawl/both-devices")
async def crawl_both(request: CrawlRequest) -> dict[str, object]:
    try:
        return await crawl_both_devices(crawler, request)
    except CrawlError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dual-device crawl failed: {exc}") from exc


@app.post("/api/monitor/crawl")
async def monitor_crawl(request: CrawlRequest) -> dict[str, object]:
    try:
        result = await crawler.crawl(request)
        stored = persist_crawl_result(history_store, str(request.url), result)
        return {"crawl": result.model_dump(), "history": stored}
    except CrawlError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Monitored crawl failed: {exc}") from exc


@app.post("/api/monitor/crawl/both-devices")
async def monitor_crawl_both(request: CrawlRequest) -> dict[str, object]:
    try:
        result = await crawl_both_devices(crawler, request)
        stored = persist_dual_crawl_result(history_store, str(request.url), result)
        return {**result, "history": stored}
    except CrawlError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Monitored dual-device crawl failed: {exc}") from exc


@app.post("/api/history/changes")
async def history_changes(payload: dict[str, object]) -> dict[str, object]:
    observations = payload.get("observations")
    if not isinstance(observations, list) or not all(isinstance(row, dict) for row in observations):
        raise HTTPException(status_code=422, detail="observations must be a list of objects")
    return detect_history_changes(observations)


@app.get("/api/history")
async def get_history(target: str) -> dict[str, object]:
    observations = history_store.load(target)
    return {"target": target, "observations": observations, "observation_count": len(observations)}


@app.post("/api/history")
async def append_history(target: str, payload: dict[str, object]) -> dict[str, object]:
    observations = payload.get("observations")
    if not isinstance(observations, list) or not all(isinstance(row, dict) for row in observations):
        raise HTTPException(status_code=422, detail="observations must be a list of objects")
    try:
        return history_store.append(target, observations)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/history/intelligence")
async def history_intelligence(target: str) -> dict[str, object]:
    return build_report_intelligence(history_store.load(target))


@app.get("/api/history/report", response_class=HTMLResponse)
async def history_report(target: str) -> HTMLResponse:
    return HTMLResponse(render_html_report(history_store.load(target), title=f"Ad Intelligence — {target}"))


@app.get("/api/history/report.pdf")
async def history_report_pdf(target: str) -> Response:
    pdf = render_pdf_report(history_store.load(target), title=f"Ad Intelligence — {target}")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="ad-intelligence-report.pdf"'})


@app.post("/api/report/intelligence")
async def report_intelligence(payload: dict[str, object]) -> dict[str, object]:
    observations = payload.get("observations")
    if not isinstance(observations, list) or not all(isinstance(row, dict) for row in observations):
        raise HTTPException(status_code=422, detail="observations must be a list of objects")
    return build_report_intelligence(observations)


@app.post("/api/report/html", response_class=HTMLResponse)
async def report_html(payload: dict[str, object]) -> HTMLResponse:
    observations = payload.get("observations")
    title = payload.get("title", "Ad Intelligence Report")
    if not isinstance(observations, list) or not all(isinstance(row, dict) for row in observations):
        raise HTTPException(status_code=422, detail="observations must be a list of objects")
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=422, detail="title must be a non-empty string")
    return HTMLResponse(render_html_report(observations, title=title.strip()))


@app.post("/api/report/pdf")
async def report_pdf(payload: dict[str, object]) -> Response:
    observations = payload.get("observations")
    title = payload.get("title", "Ad Intelligence Report")
    if not isinstance(observations, list) or not all(isinstance(row, dict) for row in observations):
        raise HTTPException(status_code=422, detail="observations must be a list of objects")
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=422, detail="title must be a non-empty string")
    try:
        pdf = render_pdf_report(observations, title=title.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="ad-intelligence-report.pdf"'})


@app.post("/api/site-crawl", response_model=SiteCrawlResult)
async def site_crawl(request: SiteCrawlRequest) -> SiteCrawlResult:
    try:
        result = await crawl_site(crawler=crawler, root_url=str(request.url), max_pages=request.max_pages,
            max_depth=request.max_depth, wait_ms=request.wait_ms, timeout_ms=request.timeout_ms,
            enrich_landing_pages=request.enrich_landing_pages, max_landing_destinations=request.max_landing_destinations)
        return SiteCrawlResult.model_validate(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Site crawl failed: {exc}") from exc


@app.get("/api/runs/{run_id}", response_model=CrawlResult)
async def get_run(run_id: str) -> CrawlResult:
    if not RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Invalid run ID")
    path = crawler.data_root / run_id / "result.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        return CrawlResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Stored run is invalid") from exc


@app.get("/api/runs/{run_id}/artifact/{artifact_name}")
async def get_artifact(run_id: str, artifact_name: str) -> FileResponse:
    if not RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Invalid run ID")
    if artifact_name not in ARTIFACTS:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = crawler.data_root / run_id / ARTIFACTS[artifact_name]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)


@app.get("/api/runs/{run_id}/image")
async def get_image(run_id: str, path: str) -> FileResponse:
    if not RUN_ID_RE.fullmatch(run_id) or not SAFE_IMAGE_RE.fullmatch(path):
        raise HTTPException(status_code=400, detail="Invalid image path")
    image_path = crawler.data_root / run_id / path
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)
