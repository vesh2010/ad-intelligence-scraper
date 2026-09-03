from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

from .crawler.crawler import SiteCrawler
from .crawler.models import CrawlRequest, CrawlResult
from .url_discovery import URLQueue


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.append(value)


def extract_page_hrefs(html: str) -> list[str]:
    parser = _HrefParser()
    parser.feed(html)
    return parser.hrefs


async def crawl_site(
    crawler: SiteCrawler,
    root_url: str,
    max_pages: int = 10,
    max_depth: int = 2,
    wait_ms: int = 1500,
    timeout_ms: int = 30000,
    enrich_landing_pages: bool = False,
    max_landing_destinations: int = 10,
) -> dict[str, Any]:
    queue = URLQueue(root_url, max_pages=max_pages)
    pages: list[CrawlResult] = []
    failures: list[dict[str, str]] = []

    while len(pages) + len(failures) < max_pages:
        item = queue.pop()
        if item is None:
            break
        depth, url = item
        try:
            result = await crawler.crawl(
                CrawlRequest(
                    url=url,
                    wait_ms=wait_ms,
                    timeout_ms=timeout_ms,
                    trace=True,
                    include_ads_txt=(depth == 0),
                    enrich_landing_pages=enrich_landing_pages,
                    max_landing_destinations=max_landing_destinations,
                )
            )
            pages.append(result)
            html_path = result.artifacts.get("html")
            if html_path and depth < max_depth:
                try:
                    with open(html_path, "r", encoding="utf-8") as handle:
                        html = handle.read()
                    hrefs = extract_page_hrefs(html)
                    queue.add_links(result.final_url, hrefs, depth)
                except OSError as exc:
                    failures.append({"url": url, "error": f"cannot read saved HTML: {exc}"})
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})

    return {
        "root_url": queue.root_url,
        "max_pages": max_pages,
        "max_depth": max_depth,
        "pages_crawled": len(pages),
        "pages_failed": len(failures),
        "pages_discovered": queue.seen_count,
        "ads_detected": sum(len(page.ad_detection.signals) if page.ad_detection else 0 for page in pages),
        "normalized_ad_records": sum(len(page.ad_records) for page in pages),
        "pages": [page.model_dump() for page in pages],
        "failures": failures,
    }
