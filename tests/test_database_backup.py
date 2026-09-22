import sqlite3
from pathlib import Path

import backup_database


def test_database_backup_creates_valid_copy(tmp_path, monkeypatch):
    source = tmp_path / "source.db"

    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO test_data (value) VALUES ('BlackSea Connect')")
        db.commit()

    monkeypatch.setattr(backup_database.app, "_owner_db_path", lambda: source)
    monkeypatch.chdir(tmp_path)

    backup_database.main()

    backups = list(Path("backups").glob("blacksea_owner-*.db"))

    assert len(backups) == 1

    with sqlite3.connect(backups[0]) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT value FROM test_data").fetchone()[0] == "BlackSea Connect"
