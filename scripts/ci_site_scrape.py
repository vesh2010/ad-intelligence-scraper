from __future__ import annotations

import asyncio
import html
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

from app.crawler.models import CrawlResult
from app.report_html import render_html_report
from app.report_intelligence import build_report_intelligence
from app.report_pdf import render_pdf_report
from app.site_crawl import crawl_site
from app.crawler.crawler import SiteCrawler


def _validate_inputs() -> dict[str, object]:
    url = os.environ["SITE_URL"]
    parsed = urlparse(url)
    max_pages = int(os.environ.get("MAX_PAGES", "50"))
    max_depth = int(os.environ.get("MAX_DEPTH", "5"))
    max_discovered = int(os.environ.get("MAX_DISCOVERED_URLS", "5000"))
    both = os.environ.get("BOTH_DEVICES", "false").lower() == "true"
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"Publisher URL must be HTTPS: {url}")
    if not 1 <= max_pages <= 500:
        raise ValueError("MAX_PAGES must be between 1 and 500")
    if not 0 <= max_depth <= 5:
        raise ValueError("MAX_DEPTH must be between 0 and 5")
    if not 1 <= max_discovered <= 20000:
        raise ValueError("MAX_DISCOVERED_URLS must be between 1 and 20000")
    return {
        "url": url,
        "max_pages": max_pages,
        "max_depth": max_depth,
        "max_discovered_urls": max_discovered,
        "both_devices": both,
    }


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


def _coverage_payload(crawls: list[dict[str, object]], max_pages: int, max_depth: int, max_discovered_urls: int) -> dict[str, object]:
    manifests = [item.get("manifest", []) for item in crawls]
    all_entries = [entry for manifest in manifests for entry in manifest if isinstance(entry, dict)]
    status_counts: dict[str, int] = {}
    type_counts: dict[str, dict[str, int]] = {}
    section_counts: dict[str, dict[str, int]] = {}
    for entry in all_entries:
        status = str(entry.get("status") or "unknown")
        page_type = str(entry.get("page_type") or "other")
        section = str(entry.get("section") or "other")
        status_counts[status] = status_counts.get(status, 0) + 1
        type_counts.setdefault(page_type, {"discovered": 0, "crawled": 0, "failed": 0})["discovered"] += 1
        if status == "success":
            type_counts[page_type]["crawled"] += 1
        if status == "failed":
            type_counts[page_type]["failed"] += 1
        section_counts.setdefault(section, {"discovered": 0, "crawled": 0, "failed": 0})["discovered"] += 1
        if status == "success":
            section_counts[section]["crawled"] += 1
        if status == "failed":
            section_counts[section]["failed"] += 1
    crawled = sum(int(item.get("pages_crawled", 0)) for item in crawls)
    successful = sum(1 for entry in all_entries if entry.get("status") == "success")
    failed = sum(1 for entry in all_entries if entry.get("status") == "failed")
    discovered = len({str(entry.get("normalized_url")) for entry in all_entries if entry.get("normalized_url")})
    return {
        "limits": {"max_pages": max_pages, "max_depth": max_depth, "max_discovered_urls": max_discovered_urls},
        "urls_discovered": discovered,
        "urls_crawled": crawled,
        "urls_successful": successful,
        "urls_failed": failed,
        "coverage_pct": round((successful / discovered * 100) if discovered else 0.0, 1),
        "maximum_depth_reached": max([int(entry.get("depth", 0)) for entry in all_entries], default=0),
        "status_counts": status_counts,
        "page_types": type_counts,
        "sections": section_counts,
        "sitemap": {
            "urls_discovered": sum(len(item.get("discovery", {}).get("sitemap_urls_discovered", [])) for item in crawls),
            "urls_crawled": sum(len(item.get("discovery", {}).get("sitemap_urls_crawled", [])) for item in crawls),
            "urls_skipped": sum(len(item.get("discovery", {}).get("sitemap_urls_skipped", [])) for item in crawls),
            "only_in_sitemap": sorted({url for item in crawls for url in item.get("discovery", {}).get("urls_found_only_in_sitemap", [])}),
            "only_through_page_links": sorted({url for item in crawls for url in item.get("discovery", {}).get("urls_found_only_through_page_links", [])}),
        },
        "manifest": all_entries,
    }


def _coverage_html(base_html: str, coverage: dict[str, object], site_url: str) -> str:
    def esc(value: object) -> str:
        return html.escape(str(value if value not in (None, "") else "—"))
    limits = coverage["limits"]
    statuses = "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in sorted(coverage["status_counts"].items())) or "<tr><td colspan='2'>No pages</td></tr>"
    types = "".join(f"<tr><td>{esc(k)}</td><td>{v['discovered']}</td><td>{v['crawled']}</td><td>{v['failed']}</td></tr>" for k, v in sorted(coverage["page_types"].items())) or "<tr><td colspan='4'>No pages</td></tr>"
    sections = "".join(f"<tr><td>{esc(k)}</td><td>{v['discovered']}</td><td>{v['crawled']}</td><td>{v['failed']}</td></tr>" for k, v in sorted(coverage["sections"].items())) or "<tr><td colspan='4'>No sections</td></tr>"
    manifest = "".join(
        f"<tr><td>{esc(e.get('url'))}</td><td>{esc(e.get('page_type'))}</td><td>{esc(e.get('section'))}</td><td>{e.get('depth', 0)}</td><td>{esc(e.get('discovery_method'))}</td><td>{esc(e.get('status'))}</td><td>{e.get('ad_signal_count', 0)}</td><td>{e.get('normalized_ad_count', 0)}</td></tr>"
        for e in coverage["manifest"]
    ) or "<tr><td colspan='8'>No manifest entries.</td></tr>"
    sitemap = coverage["sitemap"]
    appendix = f"""
<section style='font-family:system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 32px;line-height:1.45'>
<h1>Crawl coverage &amp; completeness</h1>
<p><strong>Site:</strong> {esc(site_url)}</p>
<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px'>
<div><b>URLs discovered</b><br>{coverage['urls_discovered']}</div><div><b>URLs crawled</b><br>{coverage['urls_crawled']}</div><div><b>Successful</b><br>{coverage['urls_successful']}</div><div><b>Failed</b><br>{coverage['urls_failed']}</div><div><b>Coverage</b><br>{coverage['coverage_pct']}%</div><div><b>Max depth reached</b><br>{coverage['maximum_depth_reached']}</div>
</div>
<h2>Configured limits</h2><table><tr><th>Maximum pages</th><th>Maximum depth</th><th>Maximum discovered URLs</th></tr><tr><td>{limits['max_pages']}</td><td>{limits['max_depth']}</td><td>{limits['max_discovered_urls']}</td></tr></table>
<h2>Discovery sources</h2><p>Sitemap URLs discovered: {sitemap['urls_discovered']} · crawled: {sitemap['urls_crawled']} · skipped: {sitemap['urls_skipped']}</p>
<h2>Status coverage</h2><table><tr><th>Status</th><th>Count</th></tr>{statuses}</table>
<h2>Coverage by page type</h2><table><tr><th>Page type</th><th>Discovered</th><th>Crawled</th><th>Failed</th></tr>{types}</table>
<h2>Coverage by section</h2><table><tr><th>Section</th><th>Discovered</th><th>Crawled</th><th>Failed</th></tr>{sections}</table>
<h2>Complete crawl manifest</h2><p>Every discovered URL is classified and assigned a crawl status; this distinguishes an actual no-ad result from a page that was not crawled or failed.</p>
<table><tr><th>URL</th><th>Type</th><th>Section</th><th>Depth</th><th>Discovery</th><th>Status</th><th>Ad signals</th><th>Normalized ads</th></tr>{manifest}</table>
</section>
"""
    return base_html.replace("</body>", appendix + "</body>")


def _coverage_pdf(coverage: dict[str, object], site_url: str, path: Path) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=15 * mm)
    story = [Paragraph("Crawl coverage & completeness", styles["Title"]), Paragraph(site_url, styles["BodyText"]), Spacer(1, 5 * mm)]
    story.append(Table([
        ["URLs discovered", "URLs crawled", "Successful", "Failed", "Coverage", "Max depth"],
        [str(coverage["urls_discovered"]), str(coverage["urls_crawled"]), str(coverage["urls_successful"]), str(coverage["urls_failed"]), f"{coverage['coverage_pct']}%", str(coverage["maximum_depth_reached"])],
    ], colWidths=[28 * mm] * 6, style=TableStyle([("GRID", (0,0), (-1,-1), .4, colors.grey), ("BACKGROUND", (0,0), (-1,0), colors.lightgrey), ("FONTSIZE", (0,0), (-1,-1), 7)])))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Discovery sources", styles["Heading2"]))
    s = coverage["sitemap"]
    story.append(Paragraph(f"Sitemap URLs discovered: {s['urls_discovered']}; crawled: {s['urls_crawled']}; skipped: {s['urls_skipped']}", styles["BodyText"]))
    story.append(Paragraph("Coverage by page type", styles["Heading2"]))
    data = [["Page type", "Discovered", "Crawled", "Failed"]] + [[k, str(v["discovered"]), str(v["crawled"]), str(v["failed"])] for k,v in sorted(coverage["page_types"].items())]
    story.append(Table(data, colWidths=[70*mm, 35*mm, 35*mm, 35*mm], repeatRows=1, style=TableStyle([("GRID", (0,0),(-1,-1),.4,colors.grey), ("BACKGROUND",(0,0),(-1,0),colors.lightgrey), ("FONTSIZE",(0,0),(-1,-1),7)])))
    story.append(PageBreak())
    story.append(Paragraph("Complete crawl manifest", styles["Heading2"]))
    rows = [["URL", "Type", "Section", "Depth", "Discovery", "Status", "Ads"]]
    for e in coverage["manifest"]:
        rows.append([Paragraph(str(e.get("url", ""))[:75], styles["BodyText"]), str(e.get("page_type", "")), str(e.get("section", "")), str(e.get("depth", 0)), str(e.get("discovery_method", "")), str(e.get("status", "")), str(e.get("normalized_ad_count", 0))])
    story.append(Table(rows, colWidths=[62*mm, 22*mm, 22*mm, 12*mm, 24*mm, 20*mm, 12*mm], repeatRows=1, style=TableStyle([("GRID", (0,0),(-1,-1),.3,colors.grey), ("BACKGROUND",(0,0),(-1,0),colors.lightgrey), ("FONTSIZE",(0,0),(-1,-1),6), ("VALIGN",(0,0),(-1,-1),"TOP")])) )
    doc.build(story)


def _merge_pdfs(main_pdf: Path, appendix_pdf: Path) -> None:
    writer = PdfWriter()
    for source in (main_pdf, appendix_pdf):
        reader = PdfReader(str(source))
        for page in reader.pages:
            writer.add_page(page)
    tmp = main_pdf.with_suffix(".merged.pdf")
    with tmp.open("wb") as handle:
        writer.write(handle)
    tmp.replace(main_pdf)


async def _run() -> dict[str, object]:
    cfg = _validate_inputs()
    url = str(cfg["url"])
    max_pages = int(cfg["max_pages"])
    max_depth = int(cfg["max_depth"])
    max_discovered_urls = int(cfg["max_discovered_urls"])
    both = bool(cfg["both_devices"])
    data_root = Path(os.environ.get("AD_SCRAPER_DATA_ROOT", "data/runs"))
    out = Path("ci-output")
    data_root.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    crawler = SiteCrawler(data_root)
    wait_ms = int(os.environ.get("WAIT_MS", "2500"))
    timeout_ms = int(os.environ.get("TIMEOUT_MS", "60000"))
    common = dict(max_pages=max_pages, max_depth=max_depth, max_discovered_urls=max_discovered_urls, wait_ms=wait_ms, timeout_ms=timeout_ms, enrich_landing_pages=True, max_landing_destinations=25, discover_sitemap=True, handle_consent=True, keep_evidence=True, scroll_page=True, capture_runtime_snapshots=True)
    crawls = [await crawl_site(crawler, root_url=url, device="desktop", allow_subdomains=True, **common)]
    if both:
        crawls.append(await crawl_site(crawler, root_url=url, device="mobile", allow_subdomains=True, **common))

    observations, run_ids = _collect_observations(data_root)
    intelligence = build_report_intelligence(observations)
    coverage = _coverage_payload(crawls, max_pages, max_depth, max_discovered_urls)
    report_root = out / "report"
    report_root.mkdir(parents=True, exist_ok=True)
    base_html = render_html_report(observations, title=f"Ad Intelligence Site Report — {url}")
    (report_root / "site-report.html").write_text(_coverage_html(base_html, coverage, url), encoding="utf-8")
    main_pdf = report_root / "site-report.pdf"
    main_pdf.write_bytes(render_pdf_report(observations, title=f"Ad Intelligence Site Report — {url}"))
    appendix_pdf = report_root / "coverage-appendix.pdf"
    _coverage_pdf(coverage, url, appendix_pdf)
    _merge_pdfs(main_pdf, appendix_pdf)
    appendix_pdf.unlink(missing_ok=True)

    _write_json(report_root / "crawl_manifest.json", coverage)
    _write_json(report_root / "site_summary.json", {
        "site_url": url,
        "run_ids": run_ids,
        "observation_count": intelligence.get("observation_count", len(observations)),
        "campaign_count": intelligence.get("campaigns", {}).get("campaign_count", 0),
        "competitor_count": intelligence.get("campaigns", {}).get("competitor_count", 0),
        "devices": intelligence.get("devices", {}),
        "coverage": {k: v for k, v in coverage.items() if k != "manifest"},
    })
    _write_json(out / "scrape_result.json", {"site_url": url, "run_ids": run_ids, "status": "completed", "coverage": coverage})
    _write_json(out / "run_metadata.json", {"site_url": url, "max_pages": max_pages, "max_depth": max_depth, "max_discovered_urls": max_discovered_urls, "both_devices": both, "keep_evidence": True, "run_ids": run_ids, "status": "completed"})
    _write_json(out / "crawl_results.json", crawls)
    (report_root / "index.html").write_text(
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Ad Intelligence Site Report</title></head><body><h1>Ad Intelligence Site Report</h1><p><strong>Site:</strong> {html.escape(url)}</p><ul><li><a href='site-report.html'>HTML site report</a></li><li><a href='site-report.pdf'>PDF site report</a></li><li><a href='crawl_manifest.json'>Crawl manifest JSON</a></li></ul><p>Evidence is retained under <code>data/runs/</code> for auditability.</p></body></html>", encoding="utf-8")
    if not run_ids:
        raise RuntimeError("Crawl completed without producing any result.json run")
    return {"site_url": url, "run_ids": run_ids, "coverage": {k: v for k,v in coverage.items() if k != "manifest"}}


def main() -> None:
    try:
        print(json.dumps(asyncio.run(_run()), indent=2))
    except Exception as exc:
        print(f"Ad Intelligence CI scrape failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
