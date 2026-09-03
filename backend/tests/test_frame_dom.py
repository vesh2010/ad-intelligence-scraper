from __future__ import annotations

import pytest
from playwright.async_api import async_playwright

from app.frame_dom import collect_frame_dom_candidates
from app.visual_evidence import capture_dom_ad_evidence


@pytest.mark.asyncio
async def test_collects_ad_candidate_inside_child_frame(tmp_path):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 800})
        await page.set_content(
            '<html><body>'
            '<iframe id="ad-frame" srcdoc="<div id=&quot;frame-ad&quot; class=&quot;ad-banner&quot; style=&quot;width:300px;height:250px&quot;>Sponsored</div>"></iframe>'
            '</body></html>'
        )
        await page.wait_for_timeout(50)

        candidates = await collect_frame_dom_candidates(page)
        frame_candidate = next(c for c in candidates if c.get("id") == "frame-ad")
        evidence = await capture_dom_ad_evidence(page, candidates, tmp_path)
        await browser.close()

    assert frame_candidate["frame_index"] > 0
    assert frame_candidate["frame_url"]
    assert frame_candidate["selector"] == "#frame-ad"
    captured = next(item for item in evidence if item.get("selector") == "#frame-ad")
    assert captured["frame_index"] == frame_candidate["frame_index"]
    assert captured["bbox"]["width"] == 300
