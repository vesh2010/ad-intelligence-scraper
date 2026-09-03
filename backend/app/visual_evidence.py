from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from .ad_detection import classify_dom_candidates


async def capture_dom_ad_evidence(
    page: Page,
    dom_candidates: list[dict[str, Any]],
    output_dir: str | Path,
    max_candidates: int = 40,
) -> list[dict[str, Any]]:
    """Capture screenshots and geometry for DOM candidates that look ad-related.

    This is evidence collection, not an AI visual classification step. It keeps
    expensive vision inference out of the crawler until we have a useful candidate.
    """
    run_dir = Path(output_dir)
    evidence_dir = run_dir / "ad_candidates"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    candidates = classify_dom_candidates(dom_candidates)[:max_candidates]
    results: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates, start=1):
        selector = candidate.get("selector")
        if not selector:
            continue
        locator = page.locator(str(selector)).first
        try:
            await locator.scroll_into_view_if_needed(timeout=1500)
            box = await locator.bounding_box()
            if not box or box["width"] < 20 or box["height"] < 20:
                continue
            safe_id = hashlib.sha1(str(selector).encode("utf-8")).hexdigest()[:12]
            screenshot_path = evidence_dir / f"candidate_{index:03d}_{safe_id}.png"
            await locator.screenshot(path=str(screenshot_path), animations="disabled")
            results.append({
                "candidate_index": index,
                "selector": selector,
                "tag": candidate.get("tag"),
                "id": candidate.get("id"),
                "class_name": candidate.get("class_name"),
                "text": candidate.get("text"),
                "iframe_src": candidate.get("iframe_src"),
                "bbox": {
                    "x": round(box["x"]),
                    "y": round(box["y"]),
                    "width": round(box["width"]),
                    "height": round(box["height"]),
                },
                "screenshot": str(screenshot_path),
            })
        except Exception as exc:
            results.append({
                "candidate_index": index,
                "selector": selector,
                "error": str(exc),
            })

    (run_dir / "visual_evidence.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return results
