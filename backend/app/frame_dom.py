from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import Page

from .dom_extract import DOM_SCRIPT


FRAME_EVAL_TIMEOUT_S = 2.0


async def collect_frame_dom_candidates(page: Page) -> list[dict[str, Any]]:
    """Evaluate the DOM detector in the main document and child frames with a hard per-frame bound."""
    candidates: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(page.frames):
        try:
            frame_candidates = await asyncio.wait_for(frame.evaluate(DOM_SCRIPT), timeout=FRAME_EVAL_TIMEOUT_S)
        except Exception:
            # Cross-origin, destroyed, or slow frames must never stall the whole crawl.
            continue
        if not isinstance(frame_candidates, list):
            continue
        frame_url = frame.url
        for candidate in frame_candidates:
            if not isinstance(candidate, dict):
                continue
            item = dict(candidate)
            item["frame_index"] = frame_index
            item["frame_url"] = frame_url
            candidates.append(item)
    return candidates
