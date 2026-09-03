from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def target_key(url: str) -> str:
    """Return a filesystem-safe stable key for a monitored site origin."""
    parsed = urlsplit(str(url).strip())
    origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}" if parsed.netloc else str(url).strip().lower()
    return hashlib.sha256(origin.encode("utf-8")).hexdigest()[:24]


class HistoryStore:
    """Small JSON-backed history store for local/single-instance deployments."""

    def __init__(self, root: str | Path = "data/history") -> None:
        self.root = Path(root)

    def path_for(self, target: str) -> Path:
        return self.root / f"{target_key(target)}.json"

    def load(self, target: str) -> list[dict[str, Any]]:
        path = self.path_for(target)
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []

    def append(self, target: str, observations: list[dict[str, Any]]) -> dict[str, int | str]:
        if not all(isinstance(row, dict) for row in observations):
            raise ValueError("observations must be a list of objects")
        existing = self.load(target)
        additions = [dict(row) for row in observations]
        existing.extend(additions)
        path = self.path_for(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
        return {"target": target_key(target), "observations_added": len(additions), "history_size": len(existing)}

    def clear(self, target: str) -> None:
        path = self.path_for(target)
        try:
            path.unlink()
        except FileNotFoundError:
            pass


__all__ = ["HistoryStore", "target_key"]
