from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .crawler.crawler import CrawlError, SiteCrawler
from .crawler.models import CrawlRequest, CrawlResult

app = FastAPI(title="Ad Intelligence Scraper", version="0.1.0")
crawler = SiteCrawler()


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
