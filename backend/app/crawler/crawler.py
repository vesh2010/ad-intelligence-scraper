from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from ..ad_models import AdDetectionResult
from ..ad_pipeline import detect_ads
from ..ad_reconcile import reconcile_ad_records
from ..ads_txt import fetch_ads_txt
from ..frame_dom import collect_frame_dom_candidates
from ..landing_page import enrich_ad_records
from ..runtime_ads import collect_runtime_ads
from ..visual_evidence import capture_dom_ad_evidence
from .models import CrawlRequest, CrawlResult
from .security import redact_headers


class CrawlError(RuntimeError):
    pass


class SiteCrawler:
    def __init__(self, data_root: str | Path = "data/runs") -> None:
        self.data_root = Path(data_root)

    async def crawl(self, request: CrawlRequest) -> CrawlResult:
        parsed = urlparse(str(request.url))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Only valid HTTP(S) URLs are supported")

        run_id = uuid.uuid4().hex
        run_dir = self.data_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        network_by_request: dict[int, dict[str, object]] = {}
        redirects: list[dict[str, str | int | None]] = []
        console_errors: list[str] = []
        page_errors: list[str] = []
        ad_detection = AdDetectionResult()
        runtime_snapshots: list[dict[str, object]] = []
        visual_evidence: list[dict[str, object]] = []
        ad_records = []
        landing_enrichment: dict[str, dict[str, object]] = {}
        dom_candidates: list[dict[str, object]] = []

        ads_txt: dict[str, object] | None = None
        if request.include_ads_txt:
            try:
                ads_txt = await fetch_ads_txt(str(request.url))
            except Exception as exc:
                ads_txt = {"found": False, "error": f"ads.txt fetch failed: {exc}"}

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as exc:
                raise CrawlError(
                    "Chromium could not be launched. Install it with `python -m playwright install chromium`."
                ) from exc

            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                service_workers="block",
            )
            page = await context.new_page()
            if request.trace:
                await context.tracing.start(screenshots=True, snapshots=True, sources=True)

            def on_console(message) -> None:
                if message.type == "error":
                    console_errors.append(message.text)

            def on_page_error(exc: Exception) -> None:
                page_errors.append(str(exc))

            def on_request(request_obj) -> None:
                network_by_request[id(request_obj)] = {
                    "url": request_obj.url,
                    "method": request_obj.method,
                    "resource_type": request_obj.resource_type,
                    "request_headers": redact_headers(request_obj.headers),
                    "status": None,
                    "response_headers": {},
                    "failed": False,
                }

            async def on_response(response) -> None:
                request_obj = response.request
                item = network_by_request.setdefault(
                    id(request_obj),
                    {
                        "url": response.url,
                        "method": request_obj.method,
                        "resource_type": request_obj.resource_type,
                        "request_headers": {},
                        "status": None,
                        "response_headers": {},
                        "failed": False,
                    },
                )
                item.update(
                    {
                        "url": response.url,
                        "status": response.status,
                        "response_headers": redact_headers(await response.all_headers()),
                        "failed": False,
                    }
                )
                source = request_obj.redirected_from
                if source:
                    redirects.append(
                        {"from": source.url, "to": response.url, "status": response.status}
                    )

            def on_request_failed(request_obj) -> None:
                item = network_by_request.setdefault(
                    id(request_obj),
                    {
                        "url": request_obj.url,
                        "method": request_obj.method,
                        "resource_type": request_obj.resource_type,
                        "request_headers": redact_headers(request_obj.headers),
                        "status": None,
                        "response_headers": {},
                        "failed": True,
                    },
                )
                item["failed"] = True
                if request_obj.failure:
                    item["failure_text"] = request_obj.failure

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("request", on_request)
            page.on("response", on_response)
            page.on("requestfailed", on_request_failed)

            try:
                response = await page.goto(
                    str(request.url),
                    wait_until="domcontentloaded",
                    timeout=request.timeout_ms,
                )
                await page.wait_for_timeout(request.wait_ms)

                dom_candidates = await collect_frame_dom_candidates(page)
                network = list(network_by_request.values())
                ad_detection = detect_ads(network, dom_candidates)
                runtime_snapshots.append(
                    {
                        "stage": "post_load",
                        "captured_at_ms": round((time.perf_counter() - started) * 1000),
                        "data": await collect_runtime_ads(page),
                    }
                )

                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(min(request.wait_ms, 1500))
                dom_candidates_after_scroll = await collect_frame_dom_candidates(page)
                network = list(network_by_request.values())
                scroll_detection = detect_ads(network, dom_candidates_after_scroll)
                ad_detection = self._merge_detection(ad_detection, scroll_detection)
                runtime_snapshots.append(
                    {
                        "stage": "post_scroll",
                        "captured_at_ms": round((time.perf_counter() - started) * 1000),
                        "data": await collect_runtime_ads(page),
                    }
                )

                visual_evidence = await capture_dom_ad_evidence(
                    page, dom_candidates_after_scroll, run_dir
                )
                ad_records = reconcile_ad_records(
                    ad_detection, runtime_snapshots, visual_evidence
                )
                if request.enrich_landing_pages and ad_records:
                    landing_enrichment = await enrich_ad_records(
                        ad_records, max_destinations=request.max_landing_destinations
                    )
                    for record in ad_records:
                        for destination in record.destination_urls:
                            enriched = landing_enrichment.get(destination)
                            if enriched:
                                record.landing_page = enriched
                                product = enriched.get("product")
                                if isinstance(product, dict):
                                    if not record.product_name and product.get("name"):
                                        record.product_name = str(product["name"])
                                    if not record.brand_name and product.get("brand"):
                                        record.brand_name = str(product["brand"])
                                if enriched.get("found") and "landing_page" not in record.evidence:
                                    record.evidence = [*record.evidence, "landing_page"]
                                break
                await page.evaluate("window.scrollTo(0, 0)")

                html = await page.content()
                network = list(network_by_request.values())
                await (run_dir / "page.html").write_text(html, encoding="utf-8")
                await page.screenshot(path=str(run_dir / "screenshot.png"), full_page=True)
                (run_dir / "network.json").write_text(
                    json.dumps(network, indent=2), encoding="utf-8"
                )
                (run_dir / "ads.json").write_text(
                    json.dumps(ad_detection.model_dump(), indent=2), encoding="utf-8"
                )
                (run_dir / "runtime_ads.json").write_text(
                    json.dumps(runtime_snapshots, indent=2), encoding="utf-8"
                )
                (run_dir / "ad_records.json").write_text(
                    json.dumps([record.model_dump() for record in ad_records], indent=2),
                    encoding="utf-8",
                )
                if request.enrich_landing_pages:
                    (run_dir / "landing_enrichment.json").write_text(
                        json.dumps(landing_enrichment, indent=2), encoding="utf-8"
                    )
                if ads_txt is not None:
                    (run_dir / "ads.txt.json").write_text(
                        json.dumps(ads_txt, indent=2), encoding="utf-8"
                    )

                title = await page.title()
                metadata = await page.evaluate(
                    """() => ({
                        description: document.querySelector('meta[name="description"]')?.content ?? null,
                        canonical: document.querySelector('link[rel="canonical"]')?.href ?? null,
                        lang: document.documentElement.lang || null,
                    })"""
                )
                counts = await page.evaluate(
                    """() => ({
                        images: document.images.length,
                        scripts: document.scripts.length,
                        links: document.links.length,
                        iframes: document.querySelectorAll('iframe').length,
                    })"""
                )
                dimensions = await page.evaluate(
                    """() => ({
                        viewport_width: window.innerWidth,
                        viewport_height: window.innerHeight,
                        document_width: document.documentElement.scrollWidth,
                        document_height: document.documentElement.scrollHeight,
                    })"""
                )
                frames = [frame.url for frame in page.frames]
                final_url = page.url
                status = response.status if response else None
            finally:
                if request.trace:
                    await context.tracing.stop(path=str(run_dir / "trace.zip"))
                await context.close()
                await browser.close()

        elapsed_ms = round((time.perf_counter() - started) * 1000)
        artifacts = {
            "html": str(run_dir / "page.html"),
            "screenshot": str(run_dir / "screenshot.png"),
            "network": str(run_dir / "network.json"),
            "ads": str(run_dir / "ads.json"),
            "runtime_ads": str(run_dir / "runtime_ads.json"),
            "visual_evidence": str(run_dir / "visual_evidence.json"),
            "ad_records": str(run_dir / "ad_records.json"),
        }
        if request.enrich_landing_pages:
            artifacts["landing_enrichment"] = str(run_dir / "landing_enrichment.json")
        if ads_txt is not None:
            artifacts["ads_txt"] = str(run_dir / "ads.txt.json")
        if request.trace:
            artifacts["trace"] = str(run_dir / "trace.zip")

        result = CrawlResult(
            run_id=run_id,
            requested_url=str(request.url),
            final_url=final_url,
            status=status,
            title=title,
            elapsed_ms=elapsed_ms,
            dimensions=dimensions,
            counts=counts,
            metadata=metadata,
            redirects=redirects,
            network=network,
            console_errors=console_errors,
            page_errors=page_errors,
            frames=frames,
            artifacts=artifacts,
            ad_detection=ad_detection,
            runtime_ads={"snapshots": runtime_snapshots},
            visual_evidence=visual_evidence,
            ad_records=ad_records,
            ads_txt=ads_txt,
        )
        (run_dir / "result.json").write_text(
            json.dumps(result.model_dump(), indent=2), encoding="utf-8"
        )
        return result

    @staticmethod
    def _merge_detection(left: AdDetectionResult, right: AdDetectionResult) -> AdDetectionResult:
        seen = set()
        signals = []
        for signal in [*left.signals, *right.signals]:
            key = (
                signal.signal_type,
                signal.url,
                signal.id,
                signal.host,
                signal.ad_technology,
                signal.frame_index,
                signal.frame_url,
            )
            if key in seen:
                continue
            seen.add(key)
            signals.append(signal)
        return AdDetectionResult(
            signals=signals,
            technologies=sorted({s.ad_technology for s in signals if s.ad_technology}),
            network_signal_count=sum(1 for s in signals if s.signal_type == "network"),
            dom_signal_count=sum(1 for s in signals if s.signal_type == "dom"),
        )
