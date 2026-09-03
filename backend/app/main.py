from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from .crawler.crawler import CrawlError, SiteCrawler
from .crawler.models import CrawlRequest, CrawlResult, SiteCrawlRequest, SiteCrawlResult
from .device_change import detect_history_changes
from .dual_device_crawl import crawl_both_devices
from .history_orchestration import persist_crawl_result, persist_dual_crawl_result
from .history_store import HistoryStore
from .report_html import render_html_report
from .report_intelligence import build_report_intelligence
from .report_pdf import render_pdf_report
from .site_crawl import crawl_site

app = FastAPI(title="Ad Intelligence Scraper", version="0.8.0")
crawler = SiteCrawler()
history_store = HistoryStore()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SAFE_IMAGE_RE = re.compile(r"^ad_candidates/[A-Za-z0-9_.-]+\.(?:png|jpe?g|webp)$")
ARTIFACTS = {
    "html": "page.html", "screenshot": "screenshot.png", "network": "network.json",
    "ads": "ads.json", "runtime_ads": "runtime_ads.json", "visual_evidence": "visual_evidence.json",
    "creative_assets": "creative_assets.json", "ad_records": "ad_records.json", "ads_txt": "ads.txt.json",
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
        return CrawlResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stored run is invalid: {exc}") from exc


@app.get("/api/runs/{run_id}/artifact/{artifact_name}")
async def get_artifact(run_id: str, artifact_name: str):
    if not RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Invalid run ID")
    filename = ARTIFACTS.get(artifact_name)
    if filename is None:
        raise HTTPException(status_code=404, detail="Unknown artifact")
    path = (crawler.data_root / run_id / filename).resolve()
    run_dir = (crawler.data_root / run_id).resolve()
    if run_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)


@app.get("/api/runs/{run_id}/image")
async def get_candidate_image(run_id: str, path: str):
    if not RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Invalid run ID")
    if not SAFE_IMAGE_RE.fullmatch(path):
        raise HTTPException(status_code=400, detail="Invalid image path")
    run_dir = (crawler.data_root / run_id).resolve()
    image = (run_dir / path).resolve()
    if run_dir not in image.parents or not image.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image)
