from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from .crawler.crawler import CrawlError, SiteCrawler
from .crawler.models import CrawlRequest, CrawlResult, SiteCrawlRequest, SiteCrawlResult
from .site_crawl import crawl_site

app = FastAPI(title="Ad Intelligence Scraper", version="0.3.0")
crawler = SiteCrawler()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ARTIFACTS = {
    "html": "page.html",
    "screenshot": "screenshot.png",
    "ads": "ads.json",
    "runtime_ads": "runtime_ads.json",
    "visual_evidence": "visual_evidence.json",
    "ad_records": "ad_records.json",
    "ads_txt": "ads.txt.json",
    "trace": "trace.zip",
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


@app.post("/api/site-crawl", response_model=SiteCrawlResult)
async def site_crawl(request: SiteCrawlRequest) -> SiteCrawlResult:
    try:
        result = await crawl_site(
            crawler=crawler,
            root_url=str(request.url),
            max_pages=request.max_pages,
            max_depth=request.max_depth,
            wait_ms=request.wait_ms,
            timeout_ms=request.timeout_ms,
        )
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
