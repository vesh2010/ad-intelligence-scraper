from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _identity(observation: dict[str, Any]) -> str:
    return _text(observation.get("campaign_key")) or _text(observation.get("ad_id"))


def build_campaign_intelligence(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate historical observations into explainable campaign and competitor signals."""
    campaigns: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        key = _identity(observation)
        if key:
            campaigns[key].append(observation)

    campaign_rows: list[dict[str, Any]] = []
    competitor_counts: Counter[str] = Counter()
    for key, rows in campaigns.items():
        brands = [_text(r.get("brand_name")) for r in rows if _text(r.get("brand_name"))]
        advertisers = [_text(r.get("advertiser_name")) for r in rows if _text(r.get("advertiser_name"))]
        placements = [_text(r.get("ad_unit_code")) for r in rows if _text(r.get("ad_unit_code"))]
        formats = [_text(r.get("ad_format")) for r in rows if _text(r.get("ad_format"))]
        networks = [_text(r.get("network_name")) for r in rows if _text(r.get("network_name"))]
        seen_at = [_text(r.get("observed_at")) for r in rows if _text(r.get("observed_at"))]
        devices = Counter(_text(r.get("device")) for r in rows if _text(r.get("device")))
        brand = Counter(brands).most_common(1)[0][0] if brands else None
        advertiser = Counter(advertisers).most_common(1)[0][0] if advertisers else None
        if brand:
            competitor_counts[brand] += len(rows)
        campaign_rows.append(
            {
                "campaign_key": key,
                "brand_name": brand,
                "advertiser_name": advertiser,
                "observations": len(rows),
                "observation_share_pct": round(len(rows) / len(observations) * 100, 2) if observations else 0.0,
                "first_seen": min(seen_at) if seen_at else None,
                "last_seen": max(seen_at) if seen_at else None,
                "placement_count": len(set(placements)),
                "placements": sorted(set(placements)),
                "formats": sorted(set(formats)),
                "networks": sorted(set(networks)),
                "devices": dict(sorted(devices.items())),
                "above_fold_observations": sum(r.get("above_fold") is True for r in rows),
            }
        )

    campaign_rows.sort(key=lambda row: (-row["observations"], row["campaign_key"]))
    total = len(observations)
    return {
        "campaigns": campaign_rows,
        "campaign_count": len(campaign_rows),
        "competitors": [
            {
                "brand_name": brand,
                "observations": count,
                "observation_share_pct": round(count / total * 100, 2) if total else 0.0,
            }
            for brand, count in competitor_counts.most_common()
        ],
        "total_observations": total,
    }
