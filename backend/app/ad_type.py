from __future__ import annotations

from typing import Any


STANDARD_SIZES = {
    (970, 250): "billboard",
    (970, 90): "super_leaderboard",
    (728, 90): "leaderboard",
    (468, 60): "banner",
    (320, 50): "mobile_banner",
    (320, 100): "mobile_large_banner",
    (300, 250): "medium_rectangle",
    (336, 280): "large_rectangle",
    (300, 600): "half_page",
    (160, 600): "wide_skyscraper",
    (120, 600): "skyscraper",
    (300, 50): "mobile_banner",
}


def classify_ad_type(
    *,
    width: int | None = None,
    height: int | None = None,
    position_mode: str | None = None,
    text: str | None = None,
    has_video: bool = False,
    ad_type_hint: str | None = None,
    viewport_width: int = 1440,
    viewport_height: int = 900,
) -> tuple[str, str | None]:
    if has_video or ad_type_hint in {"video", "instream", "outstream"}:
        return "video", None

    if position_mode in {"fixed", "sticky"}:
        if width and height and width >= viewport_width * 0.75 and height >= viewport_height * 0.75:
            return "interstitial", None
        return "sticky", None

    if width and height:
        format_name = STANDARD_SIZES.get((width, height))
        if format_name:
            return "display", format_name
        ratio = width / height if height else 0
        if width >= viewport_width * 0.85 and height >= 200:
            return "display", "billboard_like"
        if ratio >= 5:
            return "display", "leaderboard_like"
        if 0.8 <= ratio <= 1.5 and 200 <= width <= 500:
            return "display", "rectangle_like"

    lower = (text or "").lower()
    if any(marker in lower for marker in ("sponsored", "promoted", "advertisement")):
        return "native", "sponsored_content"
    return "unknown", None


def is_above_fold(
    *,
    y: int | None,
    height: int | None,
    viewport_height: int = 900,
) -> bool | None:
    if y is None or height is None:
        return None
    return y < viewport_height and (y + height) > 0
