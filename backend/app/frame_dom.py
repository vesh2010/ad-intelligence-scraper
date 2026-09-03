from __future__ import annotations

from typing import Any

from playwright.async_api import Page

from .dom_extract import DOM_SCRIPT


async def collect_frame_dom_candidates(page: Page) -> list[dict[str, Any]]:
    """Evaluate the DOM detector in the main document and every child frame.

    Child-frame coordinates are frame-local. Playwright later resolves the actual
    candidate screenshot/bounding box in page coordinates during evidence capture.
    """
    candidates: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(page.frames):
        try:
            frame_candidates = await frame.evaluate(DOM_SCRIPT)
        except Exception:
            # Cross-origin or rapidly destroyed frames can fail evaluation. The
            # iframe element itself remains observable from the parent document.
            continue
        frame_url = frame.url
        for candidate in frame_candidates:
            item = dict(candidate)
            item["frame_index"] = frame_index
            item["frame_url"] = frame_url
            candidates.append(item)
    return candidates
