from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _num(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _find_one(root: Path, filename: str) -> Path:
    matches = sorted(root.rglob(filename))
    if not matches:
        raise FileNotFoundError(f"{filename} not found under {root}")
    return matches[0]


def _site_summary(root: Path, key: str) -> dict[str, Any]:
    metadata = _read_json(_find_one(root, "run_metadata.json"))
    summary = _read_json(_find_one(root, "site_summary.json"))
    devices = summary.get("devices", {})
    coverage = summary.get("coverage", {})
    return {
        "key": key,
        "site_url": metadata.get("site_url", ""),
        "run_ids": metadata.get("run_ids", []),
        "observations": _num(summary.get("observation_count")),
        "campaigns": _num(summary.get("campaign_count")),
        "competitors": _num(summary.get("competitor_count")),
        "desktop_only": _num(devices.get("desktop_only_campaigns")),
        "mobile_only": _num(devices.get("mobile_only_campaigns")),
        "both_devices": _num(devices.get("both_device_campaigns")),
        "urls_discovered": _num(coverage.get("urls_discovered")),
        "urls_crawled": _num(coverage.get("urls_crawled")),
        "urls_failed": _num(coverage.get("urls_failed")),
        "coverage_pct": coverage.get("coverage_pct", 0),
        "max_depth_reached": _num(coverage.get("maximum_depth_reached")),
    }


def build_html(summaries: list[dict[str, Any]]) -> str:
    rows = "".join(
        "<tr>"
        f"<td><strong>{s['key']}</strong></td><td>{s['site_url']}</td>"
        f"<td>{s['urls_discovered']}</td><td>{s['urls_crawled']}</td><td>{s['urls_failed']}</td><td>{s['coverage_pct']}%</td>"
        f"<td>{s['observations']}</td><td>{s['campaigns']}</td><td>{s['competitors']}</td>"
        f"<td>{s['desktop_only']}</td><td>{s['mobile_only']}</td><td>{s['both_devices']}</td>"
        "</tr>"
        for s in summaries
    )
    total = {field: sum(_num(s[field]) for s in summaries) for field in ("urls_discovered", "urls_crawled", "urls_failed", "observations", "campaigns", "competitors", "desktop_only", "mobile_only", "both_devices")}
    avg_coverage = round(sum(float(s["coverage_pct"] or 0) for s in summaries) / len(summaries), 1) if summaries else 0
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>13-Site Ad Intelligence Comparison</title><style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1800px;margin:auto;padding:32px;line-height:1.45}}
table{{border-collapse:collapse;width:100%;margin:18px 0;font-size:14px}}th,td{{border:1px solid #d1d5db;padding:8px;text-align:left;vertical-align:top}}th{{background:#f3f4f6}}tfoot{{font-weight:700;background:#f9fafb}}.note{{padding:12px;border:1px solid #ddd;border-radius:8px}}
</style></head><body><h1>13-Site Ad Intelligence Comparison</h1>
<p>Automatic comparison of all 13 configured publishers. Each site uses <strong>Maximum pages per device = 5</strong>, <strong>Maximum crawl depth = 5</strong>, <strong>Maximum discovered URLs = 1,000</strong>, and desktop + mobile collection.</p>
<div class='note'>Counts are observed evidence, not market share. Advertiser/brand identity is reported only when supported by evidence and is never inferred from OCR alone. Coverage distinguishes discovered, crawled, failed and successfully observed pages.</div>
<table><thead><tr><th>Site</th><th>URL</th><th>URLs discovered</th><th>URLs crawled</th><th>URLs failed</th><th>Coverage</th><th>Ad observations</th><th>Campaigns</th><th>Competitor ads</th><th>Desktop-only</th><th>Mobile-only</th><th>Both devices</th></tr></thead><tbody>{rows}</tbody>
<tfoot><tr><td colspan='2'>Total / average</td><td>{total['urls_discovered']}</td><td>{total['urls_crawled']}</td><td>{total['urls_failed']}</td><td>{avg_coverage}% avg.</td><td>{total['observations']}</td><td>{total['campaigns']}</td><td>{total['competitors']}</td><td>{total['desktop_only']}</td><td>{total['mobile_only']}</td><td>{total['both_devices']}</td></tr></tfoot></table>
<h2>Comparison notes</h2><ul><li><strong>URLs discovered/crawled/failed</strong>: bounded crawl-manifest coverage.</li><li><strong>Ad observations</strong>: normalized rendered/runtime ad records captured.</li><li><strong>Campaigns</strong>: evidence-backed normalized campaign records.</li><li><strong>Competitor ads</strong>: advertiser/brand or external-destination evidence distinct from the publisher.</li><li><strong>Device columns</strong>: campaign distribution between desktop and mobile.</li></ul></body></html>"""


def build_pdf(summaries: list[dict[str, Any]]) -> bytes:
    from io import BytesIO
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=6.5, leading=8)
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=18, leading=22)
    story: list[Any] = [Paragraph("13-Site Ad Intelligence Comparison", title), Paragraph("Maximum 5 pages per device, crawl depth 5, maximum 1,000 discovered URLs, desktop + mobile.", small), Spacer(1, 5 * mm)]
    data = [["Site", "URL", "Discovered", "Crawled", "Failed", "Coverage", "Ads", "Campaigns", "Competitors", "Desktop", "Mobile", "Both"]]
    for s in summaries:
        data.append([Paragraph(str(s["key"]), small), Paragraph(str(s["site_url"]), small), str(s["urls_discovered"]), str(s["urls_crawled"]), str(s["urls_failed"]), f"{s['coverage_pct']}%", str(s["observations"]), str(s["campaigns"]), str(s["competitors"]), str(s["desktop_only"]), str(s["mobile_only"]), str(s["both_devices"])])
    table = Table(data, colWidths=[22*mm, 60*mm, 18*mm, 18*mm, 16*mm, 17*mm, 16*mm, 20*mm, 22*mm, 18*mm, 18*mm, 18*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f2937")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 6.5), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#d1d5db")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3), ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
    story += [table, Spacer(1, 5 * mm), Paragraph("Counts are observed evidence, not market share. Advertiser/brand identity is not inferred from OCR alone.", small)]
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), rightMargin=8*mm, leftMargin=8*mm, topMargin=10*mm, bottomMargin=10*mm, title="13-Site Ad Intelligence Comparison")
    doc.build(story)
    return out.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="site-results")
    parser.add_argument("--output", default="comparison")
    args = parser.parse_args()
    root, output = Path(args.input), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    summaries = [_site_summary(child, child.name) for child in sorted(root.iterdir()) if child.is_dir()]
    if len(summaries) != 13:
        raise SystemExit(f"Expected 13 site reports, found {len(summaries)}")
    (output / "comparison.html").write_text(build_html(summaries), encoding="utf-8")
    (output / "comparison.pdf").write_bytes(build_pdf(summaries))
    (output / "comparison.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(json.dumps({"sites": len(summaries), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
