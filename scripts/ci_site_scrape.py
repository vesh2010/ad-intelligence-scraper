from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from app.crawler.crawler import SiteCrawler
from app.crawler.models import CrawlResult
from app.report_html import render_html_report
from app.report_intelligence import build_report_intelligence
from app.report_pdf import render_pdf_report
from app.site_crawl import crawl_site


def _validate_inputs() -> tuple[str, int, int, bool]:
    url = os.environ["SITE_URL"]
    max_pages = int(os.environ.get("MAX_PAGES", "1"))
    max_depth = int(os.environ.get("MAX_DEPTH", "0"))
    both = os.environ.get("BOTH_DEVICES", "true").lower() == "true"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid site_url: {url}")
    if not 1 <= max_pages <= 25:
        raise ValueError("MAX_PAGES must be between 1 and 25")
    if not 0 <= max_depth <= 5:
        raise ValueError("MAX_DEPTH must be between 0 and 5")
    return url, max_pages, max_depth, both


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _collect_observations(data_root: Path) -> tuple[list[dict], list[str]]:
    from app.run_reports import _observations

    observations: list[dict] = []
    run_ids: list[str] = []
    for result_path in sorted(data_root.glob("*/result.json")):
        result = CrawlResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        observations.extend(_observations(result))
        run_ids.append(result.run_id)
    return observations, run_ids


def _remove_screenshot_evidence(data_root: Path) -> None:
    for path in data_root.rglob("screenshot.png"):
        path.unlink(missing_ok=True)
    for path in data_root.rglob("ad_candidates"):
        if path.is_dir():
            for screenshot in path.glob("*.png"):
                screenshot.unlink(missing_ok=True)
            for screenshot in path.glob("*.jpg"):
                screenshot.unlink(missing_ok=True)
            for screenshot in path.glob("*.jpeg"):
                screenshot.unlink(missing_ok=True)
            for screenshot in path.glob("*.webp"):
                screenshot.unlink(missing_ok=True)


def _render_site_report(data_root: Path, report_root: Path, site_url: str) -> tuple[list[str], dict]:
    observations, run_ids = _collect_observations(data_root)
    intelligence = build_report_intelligence(observations)
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "site-report.html").write_text(
        render_html_report(observations, title=f"Ad Intelligence Site Report — {site_url}"),
        encoding="utf-8",
    )
    (report_root / "site-report.pdf").write_bytes(
        render_pdf_report(observations, title=f"Ad Intelligence Site Report — {site_url}")
    )
    _write_json(report_root / "site_summary.json", {
        "site_url": site_url,
        "run_ids": run_ids,
        "observation_count": intelligence.get("observation_count", len(observations)),
        "campaign_count": intelligence.get("campaigns", {}).get("campaign_count", 0),
        "competitor_count": intelligence.get("campaigns", {}).get("competitor_count", 0),
        "devices": intelligence.get("devices", {}),
    })
    _remove_screenshot_evidence(data_root)
    return run_ids, intelligence


def _write_report_index(report_root: Path, site_url: str) -> None:
    (report_root / "index.html").write_text(
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Ad Intelligence Site Report</title><style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:auto;padding:32px;line-height:1.5}}li{{margin:14px 0}}</style></head>"
        f"<body><h1>Ad Intelligence Site Report</h1><p><strong>Site:</strong> {site_url}</p>"
        f"<ul><li><a href='site-report.html'>HTML site report</a></li><li><a href='site-report.pdf'>PDF site report</a></li></ul>"
        f"<p>Automatic report mode stores HTML/PDF reports only; screenshot evidence is intentionally not retained.</p></body></html>",
        encoding="utf-8",
    )


async def _run() -> dict[str, object]:
    url, max_pages, max_depth, both = _validate_inputs()
    data_root = Path(os.environ.get("AD_SCRAPER_DATA_ROOT", "data/runs"))
    out = Path("ci-output")
    data_root.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    crawler = SiteCrawler(data_root)
    wait_ms = int(os.environ.get("WAIT_MS", "1500"))
    timeout_ms = int(os.environ.get("TIMEOUT_MS", "30000"))

    if both:
        await crawl_site(crawler, root_url=url, max_pages=max_pages, max_depth=max_depth, wait_ms=wait_ms, timeout_ms=timeout_ms, device="desktop")
        await crawl_site(crawler, root_url=url, max_pages=max_pages, max_depth=max_depth, wait_ms=wait_ms, timeout_ms=timeout_ms, device="mobile")
    else:
        await crawl_site(crawler, root_url=url, max_pages=max_pages, max_depth=max_depth, wait_ms=wait_ms, timeout_ms=timeout_ms, device="desktop")

    run_ids, intelligence = _render_site_report(data_root, out / "report", url)
    _write_report_index(out / "report", url)
    metadata = {
        "site_url": url,
        "max_pages": max_pages,
        "max_depth": max_depth,
        "both_devices": both,
        "run_ids": run_ids,
        "observation_count": intelligence.get("observation_count", 0),
        "campaign_count": intelligence.get("campaigns", {}).get("campaign_count", 0),
        "competitor_count": intelligence.get("campaigns", {}).get("competitor_count", 0),
        "status": "completed",
    }
    _write_json(out / "scrape_result.json", metadata)
    _write_json(out / "run_metadata.json", metadata)
    if not run_ids:
        raise RuntimeError("Crawl completed without producing any result.json run")
    return metadata


def main() -> None:
    try:
        print(json.dumps(asyncio.run(_run()), indent=2))
    except Exception as exc:
        print(f"Ad Intelligence CI scrape failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
