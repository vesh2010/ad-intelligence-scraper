from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .report_intelligence import build_report_intelligence


def _text(value: Any) -> str:
    return html.escape(str(value or "—"))


def _evidence_href(path: str | None, run_id: str | None, evidence_prefix: str) -> str | None:
    if not path:
        return None
    normalized = str(path).replace("\\", "/")
    if run_id and f"/data/runs/{run_id}/" in normalized:
        return f"{evidence_prefix.rstrip('/')}/{normalized.split(f'/data/runs/{run_id}/', 1)[1]}" if evidence_prefix else normalized
    if normalized.startswith("data/runs/"):
        return f"{evidence_prefix.rstrip('/')}/{normalized}" if evidence_prefix else normalized
    return normalized


def render_html_report(
    observations: list[dict[str, Any]],
    title: str = "Ad Intelligence Report",
    evidence_prefix: str = "",
) -> str:
    """Render a self-contained intelligence report with links to retained evidence."""
    intelligence = build_report_intelligence(observations)
    campaigns = intelligence["campaigns"]["campaigns"]
    brand_frequency = intelligence["campaigns"]["competitors"]
    competitor_ads = intelligence["campaigns"].get("competitor_ads", [])
    devices = intelligence["devices"]
    history = intelligence["history"]

    campaign_rows = "".join(
        f"<tr><td>{_text(row.get('brand_name'))}</td><td>{_text(row.get('advertiser_name'))}</td>"
        f"<td>{row.get('observations', 0)}</td><td>{row.get('observation_share_pct', 0):.1f}%</td>"
        f"<td>{'Yes' if row.get('competitor') else 'No'}</td><td>{_text(row.get('first_seen'))}</td><td>{_text(row.get('last_seen'))}</td></tr>"
        for row in campaigns
    ) or "<tr><td colspan='7'>No campaigns observed.</td></tr>"

    competitor_rows = "".join(
        f"<tr><td><strong>{_text(row.get('competitor'))}</strong></td><td>{row.get('observations', 0)}</td>"
        f"<td>{row.get('observation_share_pct', 0):.1f}%</td><td>{row.get('campaign_count', 0)}</td>"
        f"<td>{_text(', '.join(row.get('evidence') or []))}</td><td>{_text(', '.join(row.get('pages_observed') or []))}</td></tr>"
        for row in competitor_ads
    ) or "<tr><td colspan='6'>No competitor ads were identified from explicit advertiser/brand or external destination evidence.</td></tr>"

    brand_rows = "".join(
        f"<tr><td>{_text(row.get('brand_name'))}</td><td>{row.get('observations', 0)}</td><td>{row.get('observation_share_pct', 0):.1f}%</td></tr>"
        for row in brand_frequency
    ) or "<tr><td colspan='3'>No brand metadata exposed.</td></tr>"

    evidence_rows: list[str] = []
    for observation in observations:
        run_id = observation.get("run_id")
        screenshot = _evidence_href(observation.get("screenshot"), run_id, evidence_prefix)
        assets = observation.get("creative_assets") or []
        asset_links = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            href = _evidence_href(asset.get("path") or asset.get("local_path"), run_id, evidence_prefix)
            if href:
                asset_links.append(f"<a href='{html.escape(href, quote=True)}'>asset</a>")
        evidence_links = []
        if screenshot:
            evidence_links.append(f"<a href='{html.escape(screenshot, quote=True)}'>screenshot</a>")
        evidence_links.extend(asset_links)
        if observation.get("run_id"):
            evidence_links.append(f"<code>{_text(observation.get('run_id'))}</code>")
        evidence_rows.append(
            f"<tr><td>{_text(observation.get('target_url'))}</td><td>{_text(observation.get('device'))}</td>"
            f"<td>{_text(observation.get('ad_type'))}</td><td>{_text(observation.get('ad_format'))}</td>"
            f"<td>{_text(observation.get('advertiser_name'))}</td><td>{_text(observation.get('brand_name'))}</td>"
            f"<td>{_text(observation.get('product_name'))}</td><td>{_text(observation.get('ad_unit_code'))}</td>"
            f"<td>{_text(observation.get('confidence'))}</td><td>{' · '.join(evidence_links) or 'No retained evidence link'}</td></tr>"
        )
    evidence_table = "".join(evidence_rows) or "<tr><td colspan='10'>No normalized ad records were observed.</td></tr>"

    change_counts = {key: history.get(key, 0) for key in (
        "new_campaigns", "disappeared_campaigns", "creative_changes", "placement_changes",
        "device_targeting_changes", "network_changes", "cpm_changes")}
    change_rows = "".join(f"<tr><td>{_text(key.replace('_', ' ').title())}</td><td>{value}</td></tr>" for key, value in change_counts.items())
    payload = html.escape(json.dumps(intelligence, indent=2, sort_keys=True, default=str))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_text(title)}</title><style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1600px;margin:0 auto;padding:32px;line-height:1.45}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0}} .card{{border:1px solid #ddd;border-radius:10px;padding:16px}} .value{{font-size:28px;font-weight:700}}
table{{border-collapse:collapse;width:100%;margin:12px 0 28px}} th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top;font-size:13px}} th{{font-weight:650}}
pre{{white-space:pre-wrap;background:#f6f6f6;padding:16px;border-radius:8px;overflow:auto}}small{{color:#666}} .badge{{display:inline-block;border:1px solid #aaa;border-radius:999px;padding:2px 8px;font-size:12px}}
</style></head><body>
<h1>{_text(title)}</h1><small>Generated from {len(observations)} observed ad records. "Share" means share of observed records, not market share.</small>
<div class="grid"><div class="card">Observations<div class="value">{intelligence['observation_count']}</div></div>
<div class="card">Campaigns<div class="value">{intelligence['campaigns']['campaign_count']}</div></div>
<div class="card">Competitor ads<div class="value">{intelligence['campaigns']['competitor_count']}</div></div>
<div class="card">Both devices<div class="value">{devices['both_device_campaigns']}</div></div><div class="card">History changes<div class="value">{history.get('change_count', 0)}</div></div></div>
<h2>Competitor advertising analysis</h2>
<p><span class="badge">{intelligence['campaigns']['competitor_count']} identified</span> These are ads attributed to an advertiser/brand or external destination distinct from the publisher. Ad-tech infrastructure domains are excluded. When a standard ad exposes only a destination domain, that domain is reported as the competitor candidate rather than guessing a brand.</p>
<table><thead><tr><th>Competitor / advertiser evidence</th><th>Ad observations</th><th>Observed share</th><th>Campaigns</th><th>Evidence</th><th>Pages</th></tr></thead><tbody>{competitor_rows}</tbody></table>
<h2>Ad inventory &amp; evidence</h2>
<p>Every normalized observation is listed here. Advertiser/brand identity remains unknown when evidence is insufficient; OCR alone is not treated as identity proof. Links point to retained screenshots/creative evidence when available.</p>
<table><thead><tr><th>Page</th><th>Device</th><th>Type</th><th>Format</th><th>Advertiser</th><th>Brand</th><th>Product</th><th>Ad unit</th><th>Confidence</th><th>Evidence</th></tr></thead><tbody>{evidence_table}</tbody></table>
<h2>Campaigns</h2><table><thead><tr><th>Brand</th><th>Advertiser</th><th>Observations</th><th>Share</th><th>Competitor</th><th>First seen</th><th>Last seen</th></tr></thead><tbody>{campaign_rows}</tbody></table>
<h2>Brand frequency</h2><table><thead><tr><th>Brand</th><th>Observations</th><th>Share</th></tr></thead><tbody>{brand_rows}</tbody></table>
<h2>Device distribution</h2><div class="grid"><div class="card">Desktop-only<div class="value">{devices['desktop_only_campaigns']}</div></div><div class="card">Mobile-only<div class="value">{devices['mobile_only_campaigns']}</div></div><div class="card">Both<div class="value">{devices['both_device_campaigns']}</div></div></div>
<h2>Historical changes</h2><table><thead><tr><th>Change type</th><th>Count</th></tr></thead><tbody>{change_rows}</tbody></table>
<h2>Machine-readable intelligence</h2><details><summary>Show JSON</summary><pre>{payload}</pre></details></body></html>"""


__all__ = ["render_html_report"]
