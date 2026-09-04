from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

from scripts.backup import create_backup


def test_create_backup_includes_sqlite_runs_and_legacy_json(tmp_path: Path) -> None:
    data = tmp_path / "data"
    history = data / "history"
    monitoring = data / "monitoring"
    runs = data / "runs" / "run-1"
    history.mkdir(parents=True)
    monitoring.mkdir(parents=True)
    runs.mkdir(parents=True)

    history_db = history / "history.sqlite3"
    with sqlite3.connect(history_db) as db:
        db.execute("create table sample (value text)")
        db.execute("insert into sample values ('history')")
    monitoring_db = monitoring / "monitoring.sqlite3"
    with sqlite3.connect(monitoring_db) as db:
        db.execute("create table sample (value text)")
        db.execute("insert into sample values ('monitoring')")

    (history / "legacy.json").write_text("[]", encoding="utf-8")
    (runs / "result.json").write_text('{"run_id":"run-1"}', encoding="utf-8")

    archive = create_backup(data)
    assert archive.is_file()
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert "history/history.sqlite3" in names
        assert "monitoring/monitoring.sqlite3" in names
        assert "runs/run-1/result.json" in names
        assert "history/legacy.json" in names
