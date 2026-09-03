from __future__ import annotations

from collections import Counter
from typing import Any


def build_intelligence_report(
    observations: list[dict[str, Any]],
    device_comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create deterministic, report-ready campaign and competitor metrics."""
    campaigns: dict[str, dict[str, Any]] = {}
    brands: Counter[str] = Counter()
    networks: Counter[str] = Counter()
    formats: Counter[str] = Counter()

    for row in observations:
        key = str(row.get("campaign_key") or row.get("ad_id") or "").strip()
        if not key:
            continue
        brand = str(row.get("brand_name") or row.get("advertiser_name") or "").strip()
        network = str(row.get("network_name") or row.get("bidder") or "").strip()
        ad_format = str(row.get("ad_format") or row.get("ad_type") or "").strip()
        if brand:
            brands[brand] += 1
        if network:
            networks[network] += 1
        if ad_format:
            formats[ad_format] += 1
        item = campaigns.setdefault(
            key,
            {
                "campaign_key": key,
                "brand": brand or None,
                "advertiser": row.get("advertiser_name"),
                "first_seen": row.get("observed_at"),
                "last_seen": row.get("observed_at"),
                "observation_count": 0,
                "placements": set(),
                "devices": set(),
            },
        )
        item["observation_count"] += 1
        if brand and not item["brand"]:
            item["brand"] = brand
        observed = row.get("observed_at")
        if observed:
            if not item["first_seen"] or str(observed) < str(item["first_seen"]):
                item["first_seen"] = observed
            if not item["last_seen"] or str(observed) > str(item["last_seen"]):
                item["last_seen"] = observed
        placement = row.get("ad_unit_code")
        if placement:
            item["placements"].add(str(placement))
        device = row.get("device")
        if device in {"desktop", "mobile"}:
            item["devices"].add(device)

    campaign_rows = []
    for item in campaigns.values():
        item["placements"] = sorted(item["placements"])
        item["devices"] = sorted(item["devices"])
        campaign_rows.append(item)
    campaign_rows.sort(key=lambda x: (-x["observation_count"], x["campaign_key"]))

    report = {
        "schema_version": "1.0",
        "observation_count": len(observations),
        "campaign_count": len(campaign_rows),
        "campaigns": campaign_rows,
        "competitors": [
            {"name": name, "observations": count}
            for name, count in brands.most_common()
        ],
        "networks": [
            {"name": name, "observations": count}
            for name, count in networks.most_common()
        ],
        "formats": [
            {"name": name, "observations": count}
            for name, count in formats.most_common()
        ],
    }
    if device_comparison is not None:
        report["device_comparison"] = device_comparison
    return report
