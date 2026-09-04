from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from app.crawler.crawler import SiteCrawler
from app.crawler.models import CrawlRequest, CrawlResult
from app.dual_device_crawl import crawl_both_devices
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


def _render_run_reports(data_root: Path, report_root: Path) -> list[str]:
    from app.run_reports import _observations

    run_ids: list[str] = []
    for result_path in sorted(data_root.glob("*/result.json")):
        result = CrawlResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        observations = _observations(result)
        run_dir = result_path.parent
        intelligence = build_report_intelligence(observations)
        (run_dir / "report.html").write_text(
            render_html_report(observations, title=f"Ad Intelligence — {result.final_url}"),
            encoding="utf-8",
        )
        (run_dir / "report.pdf").write_bytes(
            render_pdf_report(observations, title=f"Ad Intelligence — {result.final_url}")
        )
        _write_json(run_dir / "intelligence.json", intelligence)
        result.artifacts.update(
            {
                "report_html": str(run_dir / "report.html"),
                "report_pdf": str(run_dir / "report.pdf"),
                "intelligence": str(run_dir / "intelligence.json"),
            }
        )
        result_path.write_text(json.dumps(result.model_dump(), indent=2), encoding="utf-8")
        run_ids.append(result.run_id)

        public_dir = report_root / "runs" / result.run_id
        public_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "report.html",
            "report.pdf",
            "intelligence.json",
            "screenshot.png",
            "page.html",
        ):
            source = run_dir / name
            if source.is_file():
                (public_dir / name).write_bytes(source.read_bytes())
    return run_ids


def _write_report_index(report_root: Path, run_ids: list[str], site_url: str) -> None:
    links = "".join(
        f"<li><strong>{run_id}</strong> — "
        f"<a href='runs/{run_id}/report.html'>HTML report</a> · "
        f"<a href='runs/{run_id}/report.pdf'>PDF</a> · "
        f"<a href='runs/{run_id}/intelligence.json'>Intelligence JSON</a> · "
        f"<a href='runs/{run_id}/screenshot.png'>Screenshot</a></li>"
        for run_id in run_ids
    ) or "<li>No successful crawl runs were generated.</li>"
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "index.html").write_text(
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Ad Intelligence Report</title>"
        f"<style>body{{font-family:system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:32px;line-height:1.5}}li{{margin:14px 0}}</style>"
        f"</head><body><h1>Ad Intelligence Report</h1>"
        f"<p><strong>Site:</strong> {site_url}</p><ul>{links}</ul></body></html>",
        encoding="utf-8",
    )


async def _run() -> dict[str, object]:
    url, max_pages, max_depth, both = _validate_inputs()
    data_root = Path(os.environ.get("AD_SCRAPER_DATA_ROOT", "data/runs"))
    out = Path("ci-output")
    data_root.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    crawler = SiteCrawler(data_root)
    request = CrawlRequest(
        url=url,
        wait_ms=int(os.environ.get("WAIT_MS", "1500")),
        timeout_ms=int(os.environ.get("TIMEOUT_MS", "30000")),
        include_ads_txt=True,
        trace=True,
    )
    if both:
        result = await crawl_both_devices(crawler, request)
    else:
        result = await crawl_site(
            crawler,
            root_url=url,
            max_pages=max_pages,
            max_depth=max_depth,
            wait_ms=request.wait_ms,
            timeout_ms=request.timeout_ms,
        )

    _write_json(out / "scrape_result.json", result)
    run_ids = _render_run_reports(data_root, out / "report")
    _write_report_index(out / "report", run_ids, url)
    metadata = {
        "site_url": url,
        "max_pages": max_pages,
        "max_depth": max_depth,
        "both_devices": both,
        "run_ids": run_ids,
        "status": "completed",
    }
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
