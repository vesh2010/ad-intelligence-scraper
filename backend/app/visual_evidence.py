from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from .ad_detection import classify_dom_candidates


async def _candidate_locator(page: Page, candidate: dict[str, Any]):
    frames = page.frames
    frame_index = int(candidate.get("frame_index", 0))
    if frame_index < 0 or frame_index >= len(frames):
        return None
    selector = candidate.get("selector")
    if not selector:
        return None
    return frames[frame_index].locator(str(selector)).first


async def capture_dom_ad_evidence(
    page: Page,
    dom_candidates: list[dict[str, Any]],
    output_dir: str | Path,
    max_candidates: int = 40,
) -> list[dict[str, Any]]:
    """Capture screenshots and page-level geometry for DOM ad candidates.

    Evidence is collected from the correct child frame when applicable. No AI
    visual classification is performed here.
    """
    run_dir = Path(output_dir)
    evidence_dir = run_dir / "ad_candidates"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    candidates = classify_dom_candidates(dom_candidates)[:max_candidates]
    results: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates, start=1):
        selector = candidate.get("selector")
        locator = await _candidate_locator(page, candidate)
        if not selector or locator is None:
            continue
        try:
            await locator.scroll_into_view_if_needed(timeout=1500)
            box = await locator.bounding_box()
            if not box or box["width"] < 20 or box["height"] < 20:
                continue
            safe_id = hashlib.sha1(
                f"{candidate.get('frame_index', 0)}:{selector}".encode("utf-8")
            ).hexdigest()[:12]
            screenshot_path = evidence_dir / f"candidate_{index:03d}_{safe_id}.png"
            await locator.screenshot(path=str(screenshot_path), animations="disabled")
            results.append({
                "candidate_index": index,
                "frame_index": candidate.get("frame_index", 0),
                "frame_url": candidate.get("frame_url"),
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
                "frame_index": candidate.get("frame_index", 0),
                "frame_url": candidate.get("frame_url"),
                "selector": selector,
                "error": str(exc),
            })

    (run_dir / "visual_evidence.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return results
