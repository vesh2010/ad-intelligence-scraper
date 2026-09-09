from __future__ import annotations

import re
from urllib.parse import urlparse


DOM_MARKER_RE = re.compile(
    r"(?:^|[\s_:\-/])(ads?|advert(?:isement|ising)?|sponsored|promoted|adsbygoogle|commercial)(?:$|[\s_:\-/])",
    re.IGNORECASE,
)
KNOWN_AD_TECH = {
    "googlesyndication": "Google AdSense/Publisher", "doubleclick": "Google Ad Manager/DoubleClick",
    "prebid": "Prebid.js", "amazon-adsystem": "Amazon Publisher Services", "adnxs": "Microsoft/Xandr",
    "criteo": "Criteo", "rubiconproject": "Magnite/Rubicon", "pubmatic": "PubMatic", "openx": "OpenX",
    "33across": "33Across", "indexexchange": "Index Exchange", "sovrn": "Sovrn", "sharethrough": "Sharethrough",
    "triplelift": "TripleLift", "teads": "Teads", "yieldmo": "Yieldmo", "smartadserver": "Smart AdServer",
}
NETWORK_PATH_MARKERS = ("/ads/", "/ad/", "/gampad/", "/pagead/", "/adserver", "/adservice", "/adsystem/", "advertising", "/prebid")
COMMON_AD_SIZES = {
    (300, 250), (336, 280), (728, 90), (970, 90), (970, 250), (320, 50), (320, 100),
    (300, 600), (160, 600), (250, 250), (468, 60), (234, 60), (300, 100), (320, 250),
    (375, 50), (375, 100), (414, 50), (414, 100), (970, 180), (640, 360),
}


def _is_dom_ad_related(value: str) -> bool:
    return bool(DOM_MARKER_RE.search(value.strip()))


def _technology(value: str) -> str | None:
    lower = value.lower()
    for marker, name in KNOWN_AD_TECH.items():
        if marker in lower:
            return name
    return None


def _is_network_ad_related(url: str) -> bool:
    return bool(_technology(url)) or any(marker in url.lower() for marker in NETWORK_PATH_MARKERS)


def classify_network_requests(network: list[dict[str, object]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for item in network:
        url = str(item.get("url", ""))
        if not _is_network_ad_related(url):
            continue
        records.append({
            "signal_type": "network", "url": url, "host": urlparse(url).netloc,
            "method": item.get("method"), "resource_type": item.get("resource_type"),
            "status": item.get("status"), "ad_technology": _technology(url), "confidence": "medium",
        })
    return records


def classify_dom_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    """High-recall rendered-ad detection; ranking is done before the evidence cap."""
    results: list[dict[str, object]] = []
    for candidate in candidates:
        values = [candidate.get(k) for k in ("id", "class_name", "aria_label", "role", "title", "text", "alt", "iframe_src")]
        explicit = any(_is_dom_ad_related(str(value or "")) for value in values)
        dataset = candidate.get("dataset") if isinstance(candidate.get("dataset"), dict) else {}
        ad_identity = any(candidate.get(k) for k in ("advertiser_name", "brand_name", "product_name", "headline", "call_to_action"))
        has_ad_dataset = any(str(k).lower() in {
            "data-ad", "data-ad-client", "data-ad-slot", "data-ad-unit", "data-google-query-id",
            "data-advertiser", "data-advertiser-name", "data-brand", "data-brand-name", "data-product", "data-product-name",
        } for k in dataset)
        width, height = int(candidate.get("width") or 0), int(candidate.get("height") or 0)
        common_size = (width, height) in COMMON_AD_SIZES
        creative = bool(candidate.get("hrefs") or candidate.get("image_urls") or candidate.get("video_urls") or candidate.get("audio_urls") or candidate.get("video_posters"))
        iframe = str(candidate.get("tag") or "").lower() == "iframe" and bool(candidate.get("iframe_src"))
        fixed_creative = str(candidate.get("position_mode") or "") in {"fixed", "sticky"} and creative and width >= 120 and height >= 40
        semantic = bool(re.search(r"(?:ad|advert|sponsor|promo|promoted|commercial|native)", str(candidate.get("class_name") or ""), re.I))
        score = (5 if explicit else 0) + (5 if has_ad_dataset else 0) + (4 if iframe else 0) + (3 if common_size else 0) + (2 if ad_identity else 0) + (2 if fixed_creative else 0) + (1 if creative else 0) + (1 if semantic else 0)
        if score < 3:
            continue
        confidence = "high" if score >= 7 else "medium"
        results.append({**candidate, "signal_type": "dom", "confidence": confidence, "detection_score": score})
    results.sort(key=lambda item: (-int(item.get("detection_score", 0)), -int(item.get("width", 0)) * int(item.get("height", 0))))
    return results
