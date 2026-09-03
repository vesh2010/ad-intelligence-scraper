from __future__ import annotations

import html
import json
from typing import Any

from .report_intelligence import build_report_intelligence


def _text(value: Any) -> str:
    return html.escape(str(value or "—"))


def render_html_report(observations: list[dict[str, Any]], title: str = "Ad Intelligence Report") -> str:
    """Render a self-contained, evidence-backed HTML report."""
    intelligence = build_report_intelligence(observations)
    campaigns = intelligence["campaigns"]["campaigns"]
    competitors = intelligence["campaigns"]["competitors"]
    devices = intelligence["devices"]
    history = intelligence["history"]

    campaign_rows = "".join(
        f"<tr><td>{_text(row.get('brand_name'))}</td>"
        f"<td>{_text(row.get('advertiser_name'))}</td>"
        f"<td>{row.get('observations', 0)}</td>"
        f"<td>{row.get('observation_share_pct', 0):.1f}%</td>"
        f"<td>{_text(row.get('first_seen'))}</td><td>{_text(row.get('last_seen'))}</td></tr>"
        for row in campaigns
    ) or "<tr><td colspan='6'>No campaigns observed.</td></tr>"

    competitor_rows = "".join(
        f"<tr><td>{_text(row.get('brand_name'))}</td>"
        f"<td>{row.get('observations', 0)}</td>"
        f"<td>{row.get('observation_share_pct', 0):.1f}%</td></tr>"
        for row in competitors
    ) or "<tr><td colspan='3'>No competitor/brand observations.</td></tr>"

    change_counts = {
        "new_campaigns": history.get("new_campaigns", 0),
        "disappeared_campaigns": history.get("disappeared_campaigns", 0),
        "creative_changes": history.get("creative_changes", 0),
        "placement_changes": history.get("placement_changes", 0),
        "device_targeting_changes": history.get("device_targeting_changes", 0),
        "network_changes": history.get("network_changes", 0),
        "cpm_changes": history.get("cpm_changes", 0),
    }
    change_rows = "".join(
        f"<tr><td>{_text(key.replace('_', ' ').title())}</td><td>{value}</td></tr>"
        for key, value in change_counts.items()
    )

    payload = html.escape(json.dumps(intelligence, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_text(title)}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1200px;margin:0 auto;padding:32px;line-height:1.45}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0}}
.card{{border:1px solid #ddd;border-radius:10px;padding:16px}} .value{{font-size:28px;font-weight:700}}
table{{border-collapse:collapse;width:100%;margin:12px 0 28px}} th,td{{border:1px solid #ddd;padding:8px;text-align:left}} th{{font-weight:650}}
pre{{white-space:pre-wrap;background:#f6f6f6;padding:16px;border-radius:8px;overflow:auto}}
small{{color:#666}}
</style></head><body>
<h1>{_text(title)}</h1><small>Generated from {len(observations)} observed ad records. "Share" means share of observed records, not market share.</small>
<div class="grid">
<div class="card">Observations<div class="value">{intelligence['observation_count']}</div></div>
<div class="card">Campaigns<div class="value">{intelligence['campaigns']['campaign_count']}</div></div>
<div class="card">Both devices<div class="value">{devices['both_device_campaigns']}</div></div>
<div class="card">History changes<div class="value">{history.get('change_count', 0)}</div></div>
</div>
<h2>Campaigns</h2><table><thead><tr><th>Brand</th><th>Advertiser</th><th>Observations</th><th>Share</th><th>First seen</th><th>Last seen</th></tr></thead><tbody>{campaign_rows}</tbody></table>
<h2>Competitor / brand frequency</h2><table><thead><tr><th>Brand</th><th>Observations</th><th>Share</th></tr></thead><tbody>{competitor_rows}</tbody></table>
<h2>Device distribution</h2><div class="grid"><div class="card">Desktop-only<div class="value">{devices['desktop_only_campaigns']}</div></div><div class="card">Mobile-only<div class="value">{devices['mobile_only_campaigns']}</div></div><div class="card">Both<div class="value">{devices['both_device_campaigns']}</div></div></div>
<h2>Historical changes</h2><table><thead><tr><th>Change type</th><th>Count</th></tr></thead><tbody>{change_rows}</tbody></table>
<h2>Machine-readable intelligence</h2><details><summary>Show JSON</summary><pre>{payload}</pre></details>
</body></html>"""


__all__ = ["render_html_report"]
