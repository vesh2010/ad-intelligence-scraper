from __future__ import annotations

from typing import Any

from .device_compare import compare_devices
from .crawler.crawler import SiteCrawler
from .crawler.models import CrawlRequest, CrawlResult


async def crawl_both_devices(
    crawler: SiteCrawler,
    request: CrawlRequest,
) -> dict[str, Any]:
    """Run the same URL through the desktop and mobile profiles and compare results."""
    desktop_request = request.model_copy(update={"device": "desktop"})
    mobile_request = request.model_copy(update={"device": "mobile"})
    desktop, mobile = await _crawl_pair(crawler, desktop_request, mobile_request)

    observations = [
        {**record.model_dump(), "device": "desktop"}
        for record in desktop.ad_records
    ] + [
        {**record.model_dump(), "device": "mobile"}
        for record in mobile.ad_records
    ]
    return {
        "url": str(request.url),
        "desktop": desktop.model_dump(),
        "mobile": mobile.model_dump(),
        "comparison": compare_devices(observations),
    }


async def _crawl_pair(
    crawler: SiteCrawler,
    desktop_request: CrawlRequest,
    mobile_request: CrawlRequest,
) -> tuple[CrawlResult, CrawlResult]:
    # Sequential execution keeps resource use predictable and avoids cross-run interference.
    desktop = await crawler.crawl(desktop_request)
    mobile = await crawler.crawl(mobile_request)
    return desktop, mobile
