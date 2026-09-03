from __future__ import annotations

from urllib.parse import urlparse

AD_KEYWORDS = (
    "ad",
    "ads",
    "advert",
    "advertisement",
    "doubleclick",
    "googlesyndication",
    "googletagmanager",
    "prebid",
    "amazon-adsystem",
    "adnxs",
    "criteo",
    "rubiconproject",
    "pubmatic",
    "openx",
)

KNOWN_AD_TECH = {
    "googlesyndication": "Google AdSense/Publisher",
    "doubleclick": "Google Ad Manager/DoubleClick",
    "prebid": "Prebid.js",
    "amazon-adsystem": "Amazon Publisher Services",
    "adnxs": "Microsoft/Xandr",
    "criteo": "Criteo",
    "rubiconproject": "Magnite/Rubicon",
    "pubmatic": "PubMatic",
    "openx": "OpenX",
}


def _is_ad_related(value: str) -> bool:
    text = value.lower()
    return any(keyword in text for keyword in AD_KEYWORDS)


def _technology(value: str) -> str | None:
    lower = value.lower()
    for marker, name in KNOWN_AD_TECH.items():
        if marker in lower:
            return name
    return None


def classify_network_requests(network: list[dict[str, object]]) -> list[dict[str, object]]:
    """Create conservative ad-tech signals from captured network metadata.

    This intentionally reports *signals*, not proof that a particular request
    delivered a paid impression. Creative/advertiser verification is a later stage.
    """
    records: list[dict[str, object]] = []
    for item in network:
        url = str(item.get("url", ""))
        if not _is_ad_related(url):
            continue
        records.append(
            {
                "signal_type": "network",
                "url": url,
                "host": urlparse(url).netloc,
                "method": item.get("method"),
                "resource_type": item.get("resource_type"),
                "status": item.get("status"),
                "ad_technology": _technology(url),
                "confidence": "medium",
            }
        )
    return records


def classify_dom_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    """Score DOM elements supplied by the browser-side extractor."""
    results: list[dict[str, object]] = []
    for candidate in candidates:
        text = " ".join(str(candidate.get(k, "")) for k in ("id", "class_name", "aria_label", "text"))
        if not _is_ad_related(text):
            continue
        results.append({**candidate, "signal_type": "dom", "confidence": "medium"})
    return results
