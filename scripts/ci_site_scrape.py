from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from app.crawler.crawler import crawl
from app.site_crawl import crawl_site


def main() -> None:
    url = os.environ["SITE_URL"]
    max_pages = int(os.environ.get("MAX_PAGES", "1"))
    max_depth = int(os.environ.get("MAX_DEPTH", "0"))
    both = os.environ.get("BOTH_DEVICES", "true").lower() == "true"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit(f"Invalid site_url: {url}")

    out = Path("ci-output")
    out.mkdir(parents=True, exist_ok=True)

    # Use the canonical site crawler for multi-page collection. For the
    # desktop/mobile option, run one canonical page crawl per device so the
    # exact artifacts are retained in data/runs and remain UI-compatible.
    if both and max_pages == 1 and max_depth == 0:
        result = {
            "desktop": crawl(url, device="desktop"),
            "mobile": crawl(url, device="mobile"),
        }
    else:
        result = crawl_site(url, max_pages=max_pages, max_depth=max_depth)

    (out / "scrape_result.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )

    metadata = {
        "site_url": url,
        "max_pages": max_pages,
        "max_depth": max_depth,
        "both_devices": both,
        "status": "completed",
    }
    (out / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
