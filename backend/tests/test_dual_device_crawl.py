from __future__ import annotations

from pathlib import Path

import pytest

from app.ad_records import AdRecord
from app.crawler.models import CrawlRequest, CrawlResult
from app.dual_device_crawl import crawl_both_devices


class FakeCrawler:
    def __init__(self) -> None:
        self.devices: list[str] = []

    async def crawl(self, request: CrawlRequest) -> CrawlResult:
        self.devices.append(request.device)
        record = AdRecord(
            ad_id="campaign-1",
            ad_type="display",
            ad_format="banner",
            ad_unit_code="top-banner",
            destination_urls=["https://example.com/product"],
            evidence=["dom"],
        )
        return CrawlResult(
            run_id=request.device,
            requested_url=str(request.url),
            final_url=str(request.url),
            status=200,
            title="Example",
            elapsed_ms=1,
            dimensions={"viewport_width": 1440 if request.device == "desktop" else 390},
            counts={},
            metadata={},
            redirects=[],
            network=[],
            console_errors=[],
            page_errors=[],
            frames=[str(request.url)],
            artifacts={"html": str(Path("page.html"))},
            ad_records=[record],
            device=request.device,
        )


@pytest.mark.asyncio
async def test_crawl_both_devices_runs_both_profiles_and_compares() -> None:
    crawler = FakeCrawler()
    request = CrawlRequest(url="https://example.com/article")

    result = await crawl_both_devices(crawler, request)

    assert crawler.devices == ["desktop", "mobile"]
    assert result["desktop"]["device"] == "desktop"
    assert result["mobile"]["device"] == "mobile"
    assert result["comparison"]["campaign_count"] == 1
    assert result["comparison"]["both_device_campaigns"] == 1


@pytest.mark.asyncio
async def test_crawl_both_devices_does_not_mutate_request() -> None:
    crawler = FakeCrawler()
    request = CrawlRequest(url="https://example.com/article", device="mobile")

    await crawl_both_devices(crawler, request)

    assert request.device == "mobile"
