from __future__ import annotations

from typing import Any
from urllib.parse import quote


def report_export_links(target: str) -> dict[str, str]:
    """Return safe UI links for the persistent history report exports."""
    encoded = quote(str(target), safe="")
    return {
        "html": f"/api/history/report?target={encoded}",
        "pdf": f"/api/history/report.pdf?target={encoded}",
        "intelligence": f"/api/history/intelligence?target={encoded}",
    }


__all__ = ["report_export_links"]
