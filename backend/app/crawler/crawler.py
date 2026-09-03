from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

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
        network: list[dict[str, object]] = []
        redirects: list[dict[str, str | int | None]] = []
        console_errors: list[str] = []
        page_errors: list[str] = []

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as exc:
                raise CrawlError(
                    "Chromium could not be launched. Install it with "
                    "`python -m playwright install chromium` in the runtime."
                ) from exc

            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                service_workers="block",
            )
            page = await context.new_page()

            if request.trace:
                await context.tracing.start(
                    screenshots=True, snapshots=True, sources=True
                )

            def on_console(message) -> None:
                if message.type == "error":
                    console_errors.append(message.text)

            def on_page_error(exc: Exception) -> None:
                page_errors.append(str(exc))

            async def on_response(response) -> None:
                request_obj = response.request
                network.append(
                    {
                        "url": response.url,
                        "method": request_obj.method,
                        "resource_type": request_obj.resource_type,
                        "status": response.status,
                        "headers": redact_headers(await response.all_headers()),
                    }
                )
                source = response.request.redirected_from
                if source:
                    redirects.append(
                        {"from": source.url, "to": response.url, "status": response.status}
                    )

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("response", on_response)

            response = await page.goto(
                str(request.url),
                wait_until="domcontentloaded",
                timeout=request.timeout_ms,
            )
            await page.wait_for_timeout(request.wait_ms)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(min(request.wait_ms, 1500))
            await page.evaluate("window.scrollTo(0, 0)")

            html = await page.content()
            await (run_dir / "page.html").write_text(html, encoding="utf-8")
            await page.screenshot(path=str(run_dir / "screenshot.png"), full_page=True)

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

            if request.trace:
                await context.tracing.stop(path=str(run_dir / "trace.zip"))
            await context.close()
            await browser.close()

        elapsed_ms = round((time.perf_counter() - started) * 1000)
        artifacts = {
            "html": str(run_dir / "page.html"),
            "screenshot": str(run_dir / "screenshot.png"),
        }
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
        )
        (run_dir / "result.json").write_text(
            json.dumps(result.model_dump(), indent=2), encoding="utf-8"
        )
        return result
