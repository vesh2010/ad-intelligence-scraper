from __future__ import annotations

import argparse
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def backup_sqlite(source: Path, destination: Path) -> None:
    """Create a transactionally consistent SQLite backup using sqlite3.backup."""
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_db = sqlite3.connect(source)
    try:
        target_db = sqlite3.connect(destination)
        try:
            source_db.backup(target_db)
        finally:
            target_db.close()
    finally:
        source_db.close()


def create_backup(data_root: str | Path = "data", output: str | Path | None = None) -> Path:
    root = Path(data_root)
    if not root.is_dir():
        raise FileNotFoundError(f"data root does not exist: {root}")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = Path(output) if output else root / "backups" / f"ad-intelligence-{timestamp}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ad-intelligence-backup-") as temp:
        staging = Path(temp)
        for relative in ("history/history.sqlite3", "monitoring/monitoring.sqlite3"):
            backup_sqlite(root / relative, staging / relative)
        runs = root / "runs"
        if runs.is_dir():
            shutil.copytree(runs, staging / "runs", dirs_exist_ok=True)
        for relative in ("history", "monitoring"):
            source_dir = root / relative
            if source_dir.is_dir():
                for item in source_dir.glob("*.json"):
                    target = staging / relative / item.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in staging.rglob("*"):
                if item.is_file():
                    archive.write(item, item.relative_to(staging))
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up Ad Intelligence Scraper data")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    path = create_backup(args.data_root, args.output)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
