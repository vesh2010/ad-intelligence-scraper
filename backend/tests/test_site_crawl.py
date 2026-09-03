from __future__ import annotations

from pathlib import Path

import pytest

from app.crawler.models import CrawlResult
from app.site_crawl import crawl_site, extract_page_hrefs


class FakeCrawler:
    def __init__(self, html_path: Path) -> None:
        self.html_path = html_path
        self.requests: list[bool] = []

    async def crawl(self, request):
        self.requests.append(request.include_ads_txt)
        return CrawlResult(
            run_id="0123456789abcdef0123456789abcdef",
            requested_url=str(request.url),
            final_url=str(request.url),
            status=200,
            title="Test",
            elapsed_ms=1,
            dimensions={"viewport_width": 1200, "viewport_height": 800, "document_width": 1200, "document_height": 1600},
            counts={"images": 0, "scripts": 0, "links": 1, "iframes": 0},
            metadata={"description": None, "canonical": None, "lang": "en"},
            redirects=[],
            network=[],
            console_errors=[],
            page_errors=[],
            frames=[str(request.url)],
            artifacts={"html": str(self.html_path)},
            ad_detection=None,
            runtime_ads=None,
            visual_evidence=[],
            ad_records=[],
            ads_txt=None,
        )


def test_extract_page_hrefs():
    assert extract_page_hrefs('<a href="/news">News</a><a href="https://example.com/business">Business</a>') == [
        "/news",
        "https://example.com/business",
    ]


@pytest.mark.asyncio
async def test_site_crawl_only_requests_ads_txt_for_root(tmp_path: Path):
    html = tmp_path / "page.html"
    html.write_text('<a href="/news">News</a>', encoding="utf-8")
    crawler = FakeCrawler(html)

    result = await crawl_site(
        crawler, "https://example.com/", max_pages=2, max_depth=1
    )

    assert result["pages_crawled"] == 2
    assert crawler.requests == [True, False]
