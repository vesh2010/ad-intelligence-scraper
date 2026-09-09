from __future__ import annotations

import re
from typing import Any

from .crawler.crawler import SiteCrawler
from .crawler.models import CrawlRequest, CrawlResult
from .url_discovery import URLQueue, classify_page, discover_sitemaps, extract_discovery_urls, infer_section


def extract_page_hrefs(html: str) -> list[str]:
    """Backward-compatible anchor extractor used by existing integrations/tests."""
    return re.findall(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"']", html, flags=re.I)


async def crawl_site(
    crawler: SiteCrawler,
    root_url: str,
    max_pages: int = 200,
    max_depth: int = 5,
    max_discovered_urls: int = 5000,
    wait_ms: int = 2500,
    timeout_ms: int = 60000,
    enrich_landing_pages: bool = True,
    max_landing_destinations: int = 25,
    device: str = "desktop",
    discover_sitemap: bool = True,
    handle_consent: bool = True,
    keep_evidence: bool = True,
    scroll_page: bool = True,
    capture_runtime_snapshots: bool = True,
    allow_subdomains: bool = True,
) -> dict[str, Any]:
    if device not in {"desktop", "mobile"}:
        raise ValueError("device must be desktop or mobile")
    queue = URLQueue(root_url, max_pages=max_pages, max_discovered_urls=max_discovered_urls)
    pages: list[CrawlResult] = []
    failures: list[dict[str, str]] = []
    sitemap_urls: list[str] = []
    sitemap_skipped: list[dict[str, str]] = []

    if discover_sitemap and max_depth >= 1:
        try:
            sitemap_urls, sitemap_skipped = await discover_sitemaps(root_url, max_urls=max_discovered_urls)
            queue.seed_sitemap_urls(sitemap_urls, depth=1)
        except Exception as exc:
            sitemap_skipped.append({"url": root_url, "error": f"sitemap discovery failed: {exc}"})

    while len(pages) + len(failures) < max_pages:
        item = queue.pop()
        if item is None:
            break
        depth, url = item
        entry = queue.manifest.get(url, {})
        if depth > max_depth:
            entry["status"] = "skipped_limit"
            continue
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
                    device=device,
                    handle_consent=handle_consent,
                    keep_evidence=keep_evidence,
                    scroll_page=scroll_page,
                    capture_runtime_snapshots=capture_runtime_snapshots,
                )
            )
            result.depth = depth
            result.section = infer_section(result.final_url, queue.root_url)
            result.page_type = classify_page(result.final_url, result.title)
            result.discovery_method = str(entry.get("discovery_method") or "page_link")
            result_path = result.artifacts.get("html")
            failed_status = bool(result.status and result.status >= 400)
            entry.update({
                "status": "failed" if failed_status else "success",
                "http_status": result.status,
                "last_error": f"HTTP {result.status}" if failed_status else None,
                "depth": depth,
                "section": result.section,
                "page_type": result.page_type,
                "desktop_checked": device == "desktop",
                "mobile_checked": device == "mobile",
                "ad_signal_count": len(result.ad_detection.signals) if result.ad_detection else 0,
                "normalized_ad_count": len(result.ad_records),
                "run_id": result.run_id,
            })
            pages.append(result)
            if failed_status:
                failures.append({"url": url, "error": f"HTTP {result.status}", "depth": str(depth), "status": "failed"})
            elif result_path and depth < max_depth:
                try:
                    html = open(result_path, "r", encoding="utf-8").read()
                    discovered = extract_discovery_urls(result.final_url, html, queue.root_url, allow_subdomains)
                    queue.add_links(result.final_url, discovered, depth)
                except OSError as exc:
                    entry["last_error"] = f"cannot read saved HTML: {exc}"
        except Exception as exc:
            entry.update({"status": "failed", "last_error": str(exc), "depth": depth})
            failures.append({"url": url, "error": str(exc), "depth": str(depth), "status": "failed"})

    manifest = list(queue.manifest.values())
    crawled_urls = {page.requested_url for page in pages}
    failed_urls = {failure["url"] for failure in failures}
    for item in manifest:
        if item.get("url") in failed_urls:
            item["status"] = "failed"
        elif item.get("url") in crawled_urls:
            continue
        elif item.get("status") == "discovered":
            item["status"] = "queued_unvisited"
    return {
        "root_url": queue.root_url,
        "max_pages": max_pages,
        "max_depth": max_depth,
        "max_discovered_urls": max_discovered_urls,
        "device": device,
        "pages_crawled": len(pages),
        "pages_failed": len(failures),
        "pages_discovered": queue.seen_count,
        "ads_detected": sum(len(page.ad_detection.signals) if page.ad_detection else 0 for page in pages),
        "normalized_ad_records": sum(len(page.ad_records) for page in pages),
        "manifest": manifest,
        "discovery": {
            "sitemap_urls_discovered": sitemap_urls,
            "sitemap_urls_crawled": [item["url"] for item in manifest if item.get("discovery_method") == "sitemap" and item.get("status") == "success"],
            "sitemap_urls_skipped": sitemap_skipped,
            "urls_found_only_in_sitemap": sorted(set(sitemap_urls) - {item["url"] for item in manifest if item.get("discovery_method") != "sitemap"}),
            "urls_found_only_through_page_links": sorted(item["url"] for item in manifest if item.get("discovery_method") == "page_link" and item["url"] not in sitemap_urls),
        },
        "pages": [page.model_dump() for page in pages],
        "failures": failures,
    }
