from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from .ad_detection import classify_dom_candidates
from .creative_assets import capture_creative_assets


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
    capture_assets: bool = True,
) -> list[dict[str, Any]]:
    """Capture screenshots, geometry, and observed creative assets for ad candidates."""
    run_dir = Path(output_dir)
    evidence_dir = run_dir / "ad_candidates"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    candidates = classify_dom_candidates(dom_candidates)[:max_candidates]
    results: list[dict[str, Any]] = []
    asset_urls: list[str] = []

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
            candidate_images = list(candidate.get("image_urls") or [])
            candidate_videos = list(candidate.get("video_urls") or [])
            asset_urls.extend(candidate_images)
            asset_urls.extend(candidate_videos)
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
                "hrefs": candidate.get("hrefs", []),
                "image_urls": candidate_images,
                "video_urls": candidate_videos,
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

    assets = await capture_creative_assets(asset_urls, run_dir) if capture_assets else []
    asset_by_url = {str(item["url"]): item for item in assets if item.get("url")}
    for item in results:
        item["creative_assets"] = [
            asset_by_url[url]
            for url in [*(item.get("image_urls") or []), *(item.get("video_urls") or [])]
            if url in asset_by_url
        ]

    (run_dir / "creative_assets.json").write_text(
        json.dumps(assets, indent=2), encoding="utf-8"
    )
    (run_dir / "visual_evidence.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return results
