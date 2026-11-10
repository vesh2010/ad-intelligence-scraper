from __future__ import annotations

import csv
import html
import json
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urljoin, urlparse
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
AD_WAIT_MS = int(os.getenv("AD_WAIT_MS", "6000"))
PROXY_SERVER = os.getenv("PROXY_SERVER", "").strip()
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "").strip()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "")
REQUIRE_INDIA_PROXY = os.getenv("REQUIRE_INDIA_PROXY", "true").lower() == "true"
AD_SELECTORS = [
    'iframe[src*="doubleclick.net"]', 'iframe[src*="googlesyndication.com"]',
    'iframe[id*="google_ads"]', '[id^="div-gpt-ad"]', '[id*="google_ads"]',
    '[class*="ad-slot"]', '[class*="advertisement"]', '[data-ad]', '[data-testid*="ad"]',
]
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def canonical(url: str) -> str | None:
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or p.netloc.lower() not in {"www.hindustantimes.com", "hindustantimes.com"}:
        return None
    if any(x in p.path.lower() for x in ("/amp/", "/videos/shorts/")):
        return None
    if re.search(r"\.(?:jpg|jpeg|png|gif|svg|webp|pdf|mp4|xml|json)$", p.path, re.I):
        return None
    # Tracking parameters, fragments, scheme and host aliases are not new pages.
    path = p.path.rstrip("/")
    return "https://www.hindustantimes.com" + (path or "/")


def validate_proxy_geo(geo: dict) -> dict[str, str]:
    """Fail closed; a state such as Haryana alone cannot establish NCR egress."""
    country = str(geo.get("country_code", "")).upper()
    city = str(geo.get("city", "")).strip()
    region = str(geo.get("region", "")).strip()
    normalize = lambda value: re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    cities = {"delhi", "new delhi", "gurgaon", "gurugram", "noida",
              "greater noida", "ghaziabad", "faridabad"}
    delhi_regions = {"delhi", "new delhi", "nct", "nct of delhi",
                     "national capital territory of delhi"}
    if geo.get("error") or country != "IN":
        raise RuntimeError("Proxy egress is not verified in India; refusing capture.")
    if normalize(city) not in cities and normalize(region) not in delhi_regions:
        raise RuntimeError("Proxy egress is not verified as Delhi/NCR; refusing capture.")
    return {"country": country, "city": city, "region": region}


def robots_parser(context) -> RobotFileParser:
    parser = RobotFileParser()
    parser.set_url(urljoin(BASE_URL, "robots.txt"))
    try:
        response = context.request.get(parser.url, timeout=NAV_TIMEOUT_MS)
        if response.status != 200:
            raise RuntimeError("robots unavailable")
        parser.parse(response.text().splitlines())
        return parser
    except Exception:
        raise RuntimeError("Could not verify robots.txt; refusing capture.") from None



def inspect_ads(page) -> dict[str, str]:
    # Scroll to trigger lazy-loaded ad placements, then locate the first visible slot.
    page.wait_for_timeout(AD_WAIT_MS)
    try:
        page.evaluate("""() => new Promise(resolve => {
            let y = 0;
            const step = Math.max(500, Math.floor(window.innerHeight * 0.75));
            const end = Math.min(document.body.scrollHeight, step * 6);
            const tick = () => {
                window.scrollTo(0, y);
                y += step;
                if (y <= end) setTimeout(tick, 350);
                else { window.scrollTo(0, 0); resolve(); }
            };
            tick();
        })""")
        page.wait_for_timeout(1500)
        return page.evaluate("""(selectors) => {
            const nodes = new Set();
            for (const selector of selectors) {
                try { document.querySelectorAll(selector).forEach(el => nodes.add(el)); } catch (_) {}
            }
            const visible = el => {
                const r = el.getBoundingClientRect(), s = getComputedStyle(el);
                return r.width > 30 && r.height > 20 && s.display !== "none" &&
                    s.visibility !== "hidden" && Number(s.opacity) > 0 &&
                    el.getClientRects().length > 0 &&
                    (!el.checkVisibility || el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}));
            };
            // A container and its ad iframe describe one placement, not two.
            const slots = [...nodes].filter(visible).filter(el =>
                ![...nodes].some(parent => parent !== el && visible(parent) && parent.contains(el)));
            const found = slots.map(el => {
                const media = [el, ...el.querySelectorAll("img,video")];
                const evidence = media.some(m => visible(m) &&
                    ((m.tagName === "IMG" && m.complete && m.naturalWidth > 30 && m.naturalHeight > 20) ||
                     (m.tagName === "VIDEO" && m.readyState >= 2 && m.videoWidth > 30)));
                return {selector: el.id ? "#" + el.id : el.tagName.toLowerCase(),
                    top: el.getBoundingClientRect().top + window.scrollY, evidence,
                    iframe: el.tagName === "IFRAME" || !!el.querySelector("iframe")};
            });
            found.sort((a,b) => a.top - b.top);
            return {ad_slot_count: String(found.length),
                    ad_slots: found.slice(0, 10).map(x => x.selector).join("; "),
                    first_ad_top: found.length ? String(Math.round(found[0].top)) : "",
                    creative_evidence_count: String(found.filter(x => x.evidence).length),
                    creative_status: found.some(x => x.evidence) ? "loaded_media_in_ad_slot" :
                        found.some(x => x.iframe) ? "iframe_content_unverified" : "no_loaded_media_observed",
                    ad_detected: found.length ? "slot_only" : "no"};
        }""", AD_SELECTORS)
    except Exception as exc:
        return {"ad_slot_count": "0", "ad_slots": "", "first_ad_top": "",
                "ad_detected": "inspection_error: " + type(exc).__name__}


def main() -> None:
    if COUNT != 25:
        raise SystemExit("This workflow is configured for exactly 25 screenshots per run.")
    OUT.mkdir(parents=True, exist_ok=True)
    captures: list[dict[str, str]] = []
    seen: set[str] = set()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if REQUIRE_INDIA_PROXY and not PROXY_SERVER:
        raise RuntimeError("India/NCR proxy is required. Configure the PROXY_SERVER GitHub Actions secret; refusing to capture from a potentially US-based GitHub runner.")

    with sync_playwright() as p:
        proxy = {"server": PROXY_SERVER} if PROXY_SERVER else None
        if proxy and PROXY_USERNAME:
            proxy["username"] = PROXY_USERNAME
        if proxy and PROXY_PASSWORD:
            proxy["password"] = PROXY_PASSWORD
        browser = p.chromium.launch(headless=True, proxy=proxy)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            device_scale_factor=1,
            user_agent=USER_AGENT,
            ignore_https_errors=False,
        )
        page = context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        try:
            geo_response = page.goto("https://ipapi.co/json/", wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            if not geo_response or geo_response.status != 200:
                raise RuntimeError("Proxy geolocation service unavailable; refusing capture.")
            geo = geo_response.json()
            country = str(geo.get("country_code", "")).upper()
            city = str(geo.get("city", "")).strip()
            region = str(geo.get("region", "")).strip()
            if REQUIRE_INDIA_PROXY:
                validate_proxy_geo(geo)
            print(f"Verified proxy egress: country={country}, city={city}, region={region}")
            robots = robots_parser(context)
            if not robots.can_fetch(USER_AGENT, BASE_URL):
                raise RuntimeError("Homepage is disallowed by robots.txt; refusing capture.")
            response = page.goto(BASE_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            if not response or response.status >= 400:
                raise RuntimeError("Homepage did not return a successful HTTP response.")
            if canonical(page.url) != BASE_URL:
                raise RuntimeError("Homepage redirected away from the expected publisher URL.")
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
            discovered.extend(u for u in candidates if u not in discovered)

            # A second pass gathers more links from section/article pages until enough unique URLs exist.
            for seed in candidates[:12]:
                if sum(robots.can_fetch(USER_AGENT, u) for u in discovered) >= COUNT * 3:
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
                    print(f"Discovery warning for {seed}: {type(exc).__name__}")

            # Keep reserve URLs for failed navigations. Never fill with duplicates.
            targets: list[str] = []
            for url in discovered:
                if url in seen:
                    continue
                if robots and not robots.can_fetch(USER_AGENT, url):
                    continue
                seen.add(url)
                targets.append(url)
                if len(targets) == COUNT * 3:
                    break

            if not targets:
                raise RuntimeError("No pages are permitted by robots.txt for this capture.")

            if len(targets) < COUNT:
                raise RuntimeError(f"Only {len(targets)} unique permitted URLs found; need {COUNT}. No duplicate-page fallback.")

            successful = 0
            captured_urls: set[str] = set()
            for idx, url in enumerate(targets, start=1):
                if successful == COUNT:
                    break
                started = datetime.now(timezone.utc).isoformat()
                status = "ok"
                title = ""
                filename = ""
                final_url = ""
                ad_info = {"ad_detected": "not_checked", "ad_slot_count": "0", "ad_slots": ""}
                stage = "navigation"
                candidate_filename = f"{successful + 1:02d}_{stamp}.jpg"
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                    if not response or response.status >= 400:
                        raise RuntimeError(f"http_{response.status if response else 'no_response'}")
                    final_url = canonical(page.url)
                    if not final_url or final_url in captured_urls or (robots and not robots.can_fetch(USER_AGENT, final_url)):
                        raise RuntimeError("redirect_external_duplicate_or_disallowed")
                    title = page.title()
                    stage = "ad_inspection"
                    ad_info = inspect_ads(page)
                    if ad_info.get("first_ad_top"):
                        page.evaluate("(y) => window.scrollTo(0, Math.max(0, y - 120))", int(ad_info["first_ad_top"]))
                        page.wait_for_timeout(700)
                    if canonical(page.url) != final_url:
                        raise RuntimeError("redirect_during_ad_wait")
                    stage = "screenshot"
                    page.screenshot(path=str(OUT / candidate_filename), type="jpeg", quality=JPEG_QUALITY, full_page=False, animations="disabled", timeout=60000)
                    filename = candidate_filename
                    captured_urls.add(final_url)
                    successful += 1
                except PlaywrightTimeoutError:
                    status = f"{stage}_timeout"
                    # Never screenshot the preceding page after failed navigation.
                except Exception as exc:
                    status = f"error: {type(exc).__name__}"
                    if isinstance(exc, RuntimeError) and str(exc).startswith(("http_", "redirect_")):
                        status = str(exc)
                if not filename:
                    (OUT / candidate_filename).unlink(missing_ok=True)
                captures.append({
                    "index": str(idx),
                    "url": url,
                    "final_url": final_url or "",
                    "title": title,
                    "captured_at_utc": started,
                    "status": status,
                    "ad_detected": ad_info.get("ad_detected", "not_checked"),
                    "ad_slot_count": ad_info.get("ad_slot_count", "0"),
                    "ad_slots": ad_info.get("ad_slots", ""),
                    "creative_evidence_count": ad_info.get("creative_evidence_count", "0"),
                    "creative_status": ad_info.get("creative_status", "not_checked"),
                    "screenshot": filename,
                })
                print(f"[attempt {idx}; saved {successful}/{COUNT}] {status}: {url}")

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
                    f'<p>{html.escape(item["captured_at_utc"])} · {html.escape(item["status"])}</p>'
                    f'<p>Slots: {item["ad_slot_count"]} · Loaded-media evidence: {item["creative_evidence_count"]} · '
                    f'{html.escape(item["creative_status"])}</p>{image}</article>'
                )
            gallery = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hindustan Times screenshot gallery</title><style>
body{font:15px system-ui;margin:24px;background:#f4f5f7;color:#171717}header{max-width:1200px;margin:auto}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:18px;max-width:1600px;margin:24px auto}
article{background:white;padding:16px;border-radius:10px;box-shadow:0 1px 5px #0001;overflow:hidden}
img{width:100%;height:auto;border:1px solid #ddd}h2{font-size:18px}a{overflow-wrap:anywhere}
</style></head><body><header><h1>Hindustan Times · """ + str(successful) + """ viewport captures</h1>
<p>Capture batch: """ + html.escape(stamp) + f""" UTC. Screenshots are standard viewport JPEG captures. Ad slot diagnostics are in manifest.csv; a slot does not guarantee an ad creative was served.</p></header><main>""" + "".join(cards) + """</main></body></html>"""
            (OUT / "index.html").write_text(gallery, encoding="utf-8")
            (OUT / "summary.json").write_text(json.dumps({
                "site": BASE_URL, "requested_screenshots": COUNT,
                "successful_screenshots": sum(bool(x["screenshot"]) for x in captures),
                "status": "complete" if successful == COUNT else "incomplete",
                "unique_captured_urls": len(captured_urls),
                "failed_attempts": sum(x["status"] != "ok" for x in captures),
                "captured_at_utc": stamp, "captures": captures,
                "proxy_geo": {"country": country, "city": city, "region": region},
            }, indent=2), encoding="utf-8")
            if successful != COUNT:
                raise RuntimeError(f"Incomplete batch: saved {successful}/{COUNT} unique pages. See manifest.csv.")
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        # Do not emit raw browser/proxy exception messages: they can contain credentials.
        message = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        (OUT / "error.json").write_text(json.dumps({
            "status": "failed", "error_type": type(exc).__name__, "message": message,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        }, indent=2), encoding="utf-8")
        raise SystemExit(message) from None
