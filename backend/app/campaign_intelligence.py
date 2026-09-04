from __future__ import annotations

from collections import Counter, defaultdict
from urllib.parse import urlparse
from typing import Any
import re

_AD_INFRASTRUCTURE = {
    "doubleclick.net", "googlesyndication.com", "googleadservices.com", "googletagservices.com",
    "adnxs.com", "amazon-adsystem.com", "pubmatic.com", "rubiconproject.com", "openx.net",
    "criteo.com", "outbrain.com", "taboola.com", "adsrvr.org", "moatads.com", "scorecardresearch.com",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _identity(observation: dict[str, Any]) -> str:
    return _text(observation.get("campaign_key")) or _text(observation.get("ad_id"))


def _host(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    try:
        return (urlparse(raw).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _root_domain(host: str) -> str:
    parts = [p for p in host.lower().split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def _name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _looks_like_publisher(value: str, publisher: str) -> bool:
    if not value or not publisher:
        return False
    key = _name_key(value)
    domain_key = _name_key(publisher.split(".")[0])
    return bool(domain_key and (key == domain_key or domain_key in key or key in domain_key))


def _external_destination_domains(observation: dict[str, Any]) -> list[str]:
    publisher = _root_domain(_host(observation.get("publisher_domain")))
    domains: set[str] = set()
    urls = list(observation.get("destination_urls") or [])
    landing = observation.get("landing_page")
    if isinstance(landing, dict):
        urls.extend([landing.get("url"), landing.get("final_url")])
    for url in urls:
        root = _root_domain(_host(url))
        if root and root != publisher and root not in _AD_INFRASTRUCTURE:
            domains.add(root)
    return sorted(domains)


def _competitor_identity(observation: dict[str, Any]) -> tuple[str, str]:
    publisher = _root_domain(_host(observation.get("publisher_domain")))
    for field, kind in (("advertiser_name", "advertiser"), ("brand_name", "brand")):
        value = _text(observation.get(field))
        if value and not _looks_like_publisher(value, publisher):
            return value, kind
    domains = _external_destination_domains(observation)
    if domains:
        return domains[0], "destination_domain"
    return "", ""


def build_campaign_intelligence(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate observable ads into campaign, creative, brand and competitor intelligence."""
    campaigns: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        key = _identity(observation)
        if key:
            campaigns[key].append(observation)

    campaign_rows: list[dict[str, Any]] = []
    brand_counts: Counter[str] = Counter()
    competitor_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, rows in campaigns.items():
        brands = [_text(r.get("brand_name")) for r in rows if _text(r.get("brand_name"))]
        advertisers = [_text(r.get("advertiser_name")) for r in rows if _text(r.get("advertiser_name"))]
        products = [_text(r.get("product_name")) for r in rows if _text(r.get("product_name"))]
        placements = [_text(r.get("ad_unit_code")) for r in rows if _text(r.get("ad_unit_code"))]
        formats = [_text(r.get("ad_format")) for r in rows if _text(r.get("ad_format"))]
        networks = [_text(r.get("network_name")) for r in rows if _text(r.get("network_name"))]
        seen_at = [_text(r.get("observed_at")) for r in rows if _text(r.get("observed_at"))]
        devices = Counter(_text(r.get("device")) for r in rows if _text(r.get("device")))
        ocr = [_text(r.get("ocr_text")) for r in rows if _text(r.get("ocr_text"))]
        ctas = [cta for r in rows for cta in (r.get("call_to_action") or []) if _text(cta)]
        brand = Counter(brands).most_common(1)[0][0] if brands else None
        advertiser = Counter(advertisers).most_common(1)[0][0] if advertisers else None
        product = Counter(products).most_common(1)[0][0] if products else None
        if brand:
            brand_counts[brand] += len(rows)
        labels = [(label, kind) for label, kind in (_competitor_identity(row) for row in rows) if label]
        competitor_label = Counter(label for label, _ in labels).most_common(1)[0][0] if labels else None
        competitor_evidence = sorted({kind for label, kind in labels if label == competitor_label})
        if competitor_label:
            competitor_groups[competitor_label].extend(rows)
        campaign_rows.append({
            "campaign_key": key, "brand_name": brand, "advertiser_name": advertiser, "product_name": product,
            "observations": len(rows),
            "observation_share_pct": round(len(rows) / len(observations) * 100, 2) if observations else 0.0,
            "first_seen": min(seen_at) if seen_at else None, "last_seen": max(seen_at) if seen_at else None,
            "placement_count": len(set(placements)), "placements": sorted(set(placements)),
            "formats": sorted(set(formats)), "networks": sorted(set(networks)), "devices": dict(sorted(devices.items())),
            "above_fold_observations": sum(r.get("above_fold") is True for r in rows),
            "ocr_text": ocr[:3], "call_to_action": sorted(set(ctas)),
            "creative_kinds": sorted({str((r.get("visual_classification") or {}).get("creative_kind")) for r in rows if (r.get("visual_classification") or {}).get("creative_kind")}),
            "screenshot_evidence": sorted({str(r.get("screenshot")) for r in rows if r.get("screenshot")}),
            "creative_image_urls": sorted({u for r in rows for u in (r.get("creative_image_urls") or []) if u}),
            "creative_video_urls": sorted({u for r in rows for u in (r.get("creative_video_urls") or []) if u}),
            "creative_audio_urls": sorted({u for r in rows for u in (r.get("creative_audio_urls") or []) if u}),
            "competitor": bool(competitor_label), "competitor_label": competitor_label, "competitor_evidence": competitor_evidence,
        })

    campaign_rows.sort(key=lambda row: (-row["observations"], row["campaign_key"]))
    total = len(observations)
    competitor_ads: list[dict[str, Any]] = []
    for label, rows in competitor_groups.items():
        pages = sorted({(_text(r.get("target_url")) or _text(r.get("publisher_domain"))) for r in rows if _text(r.get("target_url")) or _text(r.get("publisher_domain"))})
        campaign_keys = sorted({_identity(r) for r in rows if _identity(r)})
        evidence = sorted({kind for r in rows for label2, kind in [_competitor_identity(r)] if label2 == label and kind})
        competitor_ads.append({
            "competitor": label, "advertiser_name": label, "observations": len(rows),
            "observation_share_pct": round(len(rows) / total * 100, 2) if total else 0.0,
            "campaign_count": len(campaign_keys), "campaign_keys": campaign_keys, "pages_observed": pages, "evidence": evidence,
            "ocr_text": sorted({_text(r.get("ocr_text")) for r in rows if _text(r.get("ocr_text"))})[:5],
            "products": sorted({_text(r.get("product_name")) for r in rows if _text(r.get("product_name"))}),
            "screenshots": sorted({str(r.get("screenshot")) for r in rows if r.get("screenshot")}),
        })
    competitor_ads.sort(key=lambda row: (-row["observations"], row["competitor"]))
    return {
        "campaigns": campaign_rows, "campaign_count": len(campaign_rows),
        "competitors": [{"brand_name": brand, "observations": count, "observation_share_pct": round(count / total * 100, 2) if total else 0.0} for brand, count in brand_counts.most_common()],
        "competitor_ads": competitor_ads, "competitor_count": len(competitor_ads), "total_observations": total,
    }
