from __future__ import annotations

import csv
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://www.hindustantimes.com/"
RUN_LOCAL = datetime.now(ZoneInfo("Asia/Kolkata"))
RUN_DATE = RUN_LOCAL.strftime("%Y-%m-%d")
RUN_TIME = RUN_LOCAL.strftime("%H-%M-%S")
OUT = Path("screenshots") / RUN_DATE / RUN_TIME
COUNT = int(os.getenv("SCREENSHOT_COUNT", "25"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "70"))
NAV_TIMEOUT_MS = int(os.getenv("NAV_TIMEOUT_MS", "30000"))
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def canonical(url: str) -> str | None:
    url = urldefrag(url)[0]
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or p.netloc.lower() not in {"www.hindustantimes.com", "hindustantimes.com"}:
        return None
    if any(x in p.path.lower() for x in ("/amp/", "/videos/shorts/")):
        return None
    return url.rstrip("/") or BASE_URL


def robots_parser() -> RobotFileParser | None:
    parser = RobotFileParser()
    parser.set_url(urljoin(BASE_URL, "robots.txt"))
    try:
        parser.read()
        return parser
    except Exception as exc:
        print(f"WARNING: could not read robots.txt ({exc}); limiting capture to discovered public pages")
        return None


def main() -> None:
    if COUNT != 25:
        raise SystemExit("This workflow is configured for exactly 25 screenshots per run.")
    OUT.mkdir(parents=True, exist_ok=True)
    captures: list[dict[str, str]] = []
    seen: set[str] = set()
    robots = robots_parser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            device_scale_factor=1,
            user_agent=USER_AGENT,
            ignore_https_errors=False,
        )
        page = context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        try:
            response = page.goto(BASE_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            if response and response.status >= 400:
                raise RuntimeError(f"Homepage returned HTTP {response.status}")
            page.wait_for_timeout(2500)
            try:
                page.locator("body").evaluate("(el) => el.innerText")
            except Exception:
                pass

            discovered: list[str] = [BASE_URL]
            # Collect links from the rendered page, prioritizing editorial and section URLs.
            hrefs = page.locator("a[href]").evaluate_all("(els) => els.map(a => a.href)")
            candidates: list[str] = []
            for href in hrefs:
                normalized = canonical(href)
                if normalized and normalized not in candidates:
                    candidates.append(normalized)
            candidates.sort(key=lambda u: (0 if re.search(r"/(india|world|business|technology|sports|entertainment|cities|lifestyle|education|opinion|photos|cricket|latest-news)/", urlparse(u).path, re.I) else 1, len(u)))
            discovered.extend(candidates)

            # A second pass gathers more links from section/article pages until enough unique URLs exist.
            for seed in candidates[:12]:
                if len(discovered) >= COUNT * 3:
                    break
                if robots and not robots.can_fetch(USER_AGENT, seed):
                    continue
                try:
                    page.goto(seed, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                    page.wait_for_timeout(900)
                    extra = page.locator("a[href]").evaluate_all("(els) => els.map(a => a.href)")
                    for href in extra:
                        normalized = canonical(href)
                        if normalized and normalized not in discovered:
                            discovered.append(normalized)
                except Exception as exc:
                    print(f"Discovery warning for {seed}: {exc}")

            # Capture unique pages first. If the publisher exposes fewer than 25 crawlable URLs,
            # repeat the homepage at fresh intervals to still provide 25 timestamped observations.
            targets: list[str] = []
            for url in discovered:
                if url in seen:
                    continue
                if robots and not robots.can_fetch(USER_AGENT, url):
                    continue
                seen.add(url)
                targets.append(url)
                if len(targets) == COUNT:
                    break

            if not targets:
                raise RuntimeError("No pages are permitted by robots.txt for this capture.")

            while len(targets) < COUNT:
                targets.append(BASE_URL)

            for idx, url in enumerate(targets, start=1):
                started = datetime.now(timezone.utc).isoformat()
                status = "ok"
                title = ""
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                    if response and response.status >= 400:
                        status = f"http_{response.status}"
                    page.wait_for_timeout(1200)
                    title = page.title()
                    # Full-page capture includes the currently rendered page, not just the viewport.
                    filename = f"{idx:02d}_{stamp}.jpg"
                    page.screenshot(path=str(OUT / filename), type="jpeg", quality=JPEG_QUALITY, full_page=True, animations="disabled", timeout=60000)
                except PlaywrightTimeoutError:
                    status = "navigation_timeout"
                    filename = f"{idx:02d}_{stamp}.jpg"
                    page.screenshot(path=str(OUT / filename), type="jpeg", quality=JPEG_QUALITY, full_page=True, animations="disabled", timeout=60000)
                except Exception as exc:
                    status = f"error: {type(exc).__name__}: {exc}"
                    filename = ""
                captures.append({
                    "index": str(idx),
                    "url": url,
                    "title": title,
                    "captured_at_utc": started,
                    "status": status,
                    "screenshot": filename,
                })
                print(f"[{idx}/{COUNT}] {status}: {url}")

            with (OUT / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(captures[0].keys()))
                writer.writeheader()
                writer.writerows(captures)

            cards = []
            for item in captures:
                image = f'<img src="{html.escape(item["screenshot"])}" loading="lazy" alt="Capture {item["index"]}">' if item["screenshot"] else "<p>Screenshot unavailable</p>"
                cards.append(
                    f'<article><h2>#{item["index"]} · {html.escape(item["title"] or "Untitled page")}</h2>'
                    f'<p><a href="{html.escape(item["url"])}">{html.escape(item["url"])}</a></p>'
                    f'<p>{html.escape(item["captured_at_utc"])} · {html.escape(item["status"])}</p>{image}</article>'
                )
            gallery = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hindustan Times screenshot gallery</title><style>
body{font:15px system-ui;margin:24px;background:#f4f5f7;color:#171717}header{max-width:1200px;margin:auto}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:18px;max-width:1600px;margin:24px auto}
article{background:white;padding:16px;border-radius:10px;box-shadow:0 1px 5px #0001;overflow:hidden}
img{width:100%;height:auto;border:1px solid #ddd}h2{font-size:18px}a{overflow-wrap:anywhere}
</style></head><body><header><h1>Hindustan Times · 25 full-page captures</h1>
<p>Capture batch: """ + html.escape(stamp) + f""" UTC. Screenshots are full-page browser captures of publicly accessible same-site pages.</p></header><main>""" + "".join(cards) + """</main></body></html>"""
            (OUT / "index.html").write_text(gallery, encoding="utf-8")
            (OUT / "summary.json").write_text(json.dumps({
                "site": BASE_URL, "requested_screenshots": COUNT,
                "successful_screenshots": sum(bool(x["screenshot"]) for x in captures),
                "captured_at_utc": stamp, "captures": captures,
            }, indent=2), encoding="utf-8")
            if sum(bool(x["screenshot"]) for x in captures) == 0:
                raise RuntimeError("No screenshots were successfully saved.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
