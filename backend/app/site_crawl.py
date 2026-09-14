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
    trace: bool = False,
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
                    trace=trace,
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
                "url": result.requested_url,
                "normalized_url": result.final_url,
                "depth": depth,
                "section": result.section,
                "page_type": result.page_type,
                "status": "failed" if failed_status else "success",
                "http_status": result.status,
                "ad_signal_count": len(result.ad_detection.signals),
                "normalized_ad_count": len(result.ad_records),
                "errors": [*result.console_errors, *result.page_errors],
                "evidence_paths": list(result.artifacts.values()),
            })
            if failed_status:
                failures.append({"url": url, "error": f"HTTP {result.status}"})
            else:
                pages.append(result)
            discovered = extract_discovery_urls(result, current_url=result.final_url, root_url=queue.root_url)
            queue.add_many(discovered, depth=depth + 1, discovery_method="page_link")
        except Exception as exc:
            entry.update({"status": "failed", "errors": [str(exc)]})
            failures.append({"url": url, "error": str(exc)})

    manifest = list(queue.manifest.values())
    return {
        "site_url": root_url,
        "device": device,
        "crawl_settings": {
            "max_pages": max_pages, "max_depth": max_depth, "max_discovered_urls": max_discovered_urls,
            "wait_ms": wait_ms, "timeout_ms": timeout_ms, "enrich_landing_pages": enrich_landing_pages,
            "max_landing_destinations": max_landing_destinations, "discover_sitemap": discover_sitemap,
            "handle_consent": handle_consent, "keep_evidence": keep_evidence, "scroll_page": scroll_page,
            "capture_runtime_snapshots": capture_runtime_snapshots, "allow_subdomains": allow_subdomains, "trace": trace,
        },
        "pages_crawled": len(pages) + len(failures), "pages_successful": len(pages), "pages_failed": len(failures),
        "pages_discovered": queue.discovered_count, "ads_detected": sum(len(p.ad_detection.signals) for p in pages),
        "ads_normalized": sum(len(p.ad_records) for p in pages), "manifest": manifest,
        "discovery": {
            "sitemap_urls_discovered": sitemap_urls, "sitemap_urls_crawled": [], "sitemap_urls_skipped": sitemap_skipped,
            "urls_found_only_in_sitemap": sorted(set(sitemap_urls) - {p.requested_url for p in pages}),
            "urls_found_only_through_page_links": [],
        },
        "pages": [p.model_dump() for p in pages], "failures": failures,
    }
