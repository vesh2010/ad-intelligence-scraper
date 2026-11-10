"""Validate one capture batch, not a recursive count across unrelated batches."""
from __future__ import annotations

import csv
import json
import struct
import sys
from pathlib import Path

try:
    from .capture_hindustan_times import canonical, validate_proxy_geo
except ImportError:
    from capture_hindustan_times import canonical, validate_proxy_geo


def jpeg_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            raise ValueError("Not a JPEG")
        while True:
            if handle.read(1) != b"\xff":
                raise ValueError("Invalid JPEG marker")
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if not marker or marker in (b"\xd9", b"\xda"):
                raise ValueError("JPEG has no dimensions")
            length_bytes = handle.read(2)
            if len(length_bytes) != 2:
                raise ValueError("Truncated JPEG")
            length = struct.unpack(">H", length_bytes)[0]
            if length < 2:
                raise ValueError("Invalid JPEG segment length")
            if marker[0] in {0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7,
                             0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf}:
                _, height, width = struct.unpack(">BHH", handle.read(5))
                return width, height
            handle.seek(length - 2, 1)


def validate_batch(root: Path) -> None:
    summaries = list(root.rglob("summary.json"))
    if len(summaries) != 1:
        raise ValueError("Expected exactly one summary.json")
    folder = summaries[0].parent
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    if summary.get("status") != "complete" or summary.get("successful_screenshots") != 25:
        raise ValueError("Batch is incomplete")
    geo = summary.get("proxy_geo", {})
    validate_proxy_geo({"country_code": geo.get("country"), **geo})
    with (folder / "manifest.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if rows != summary.get("captures"):
        raise ValueError("Manifest and summary captures disagree")
    saved = [row for row in rows if row.get("screenshot")]
    urls = [canonical(row.get("final_url", "")) for row in saved]
    if len(saved) != 25 or None in urls or len(set(urls)) != 25:
        raise ValueError("Expected 25 unique Hindustan Times pages")
    names = [row["screenshot"] for row in saved]
    if len(set(names)) != 25 or any(Path(name).name != name for name in names):
        raise ValueError("Screenshot filenames are duplicated or unsafe")
    images = list(root.rglob("*.jpg"))
    if len(images) != 25 or set(images) != {folder / name for name in names}:
        raise ValueError("Manifest does not match JPEG files")
    for row in saved:
        if row["status"] != "ok" or jpeg_dimensions(folder / row["screenshot"]) != (1440, 1000):
            raise ValueError("Invalid capture status or viewport dimensions")
    gallery = (folder / "index.html").read_text(encoding="utf-8")
    if any(f'src="{name}"' not in gallery for name in names):
        raise ValueError("Gallery is missing screenshot references")


if __name__ == "__main__":
    validate_batch(Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots"))
    print("Validated 25 unique Hindustan Times pages, 1440 x 1000 JPEGs, reports and NCR egress.")
