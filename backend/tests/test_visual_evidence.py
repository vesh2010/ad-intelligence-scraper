from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from app.dom_extract import DOM_SCRIPT
from app.visual_evidence import capture_dom_ad_evidence


@pytest.mark.asyncio
async def test_dom_candidate_screenshot_is_saved(tmp_path: Path) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 800})
        await page.set_content(
            '<html><body style="margin:0;height:1600px">'
            '<div style="height:500px"></div>'
            '<div id="top-ad" class="ad-banner" style="width:728px;height:90px">Buy now</div>'
            '<div style="height:900px"></div>'
            '</body></html>'
        )
        candidates = await page.evaluate(DOM_SCRIPT)
        evidence = await capture_dom_ad_evidence(page, candidates, tmp_path)
        await browser.close()

    assert len(evidence) == 1
    assert evidence[0]["selector"] == "#top-ad"
    screenshot = Path(evidence[0]["screenshot"])
    assert screenshot.is_file()
    assert screenshot.stat().st_size > 0
