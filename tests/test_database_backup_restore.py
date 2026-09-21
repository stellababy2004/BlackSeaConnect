import sqlite3
from pathlib import Path

import pytest

from scripts.backup_database import create_backup, _integrity_check
from scripts.restore_database import restore_database


def _create_database(path: Path, value: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def _read_value(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT value FROM sample ORDER BY id LIMIT 1").fetchone()
    return row[0]


def test_backup_creates_valid_database_with_expected_data(tmp_path):
    source = tmp_path / "source database.db"
    destination = tmp_path / "backups"

    _create_database(source, "expected")

    backup = create_backup(source, destination)

    assert backup.exists()
    assert _read_value(backup) == "expected"
    _integrity_check(backup)


def test_restore_recovers_expected_data(tmp_path):
    source = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    target = tmp_path / "restored.db"

    _create_database(source, "original")
    backup = create_backup(source, backup_dir)

    restore_database(backup, target)

    assert target.exists()
    assert _read_value(target) == "original"


def test_restore_refuses_existing_target_without_force(tmp_path):
    source = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    target = tmp_path / "target.db"

    _create_database(source, "source")
    _create_database(target, "target")
    backup = create_backup(source, backup_dir)

    with pytest.raises(FileExistsError):
        restore_database(backup, target)

    assert _read_value(target) == "target"


def test_restore_force_creates_safety_copy(tmp_path):
    source = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    target = tmp_path / "target.db"

    _create_database(source, "restored")
    _create_database(target, "before")
    backup = create_backup(source, backup_dir)

    safety_copy = restore_database(backup, target, force=True)

    assert safety_copy is not None
    assert safety_copy.exists()
    assert _read_value(safety_copy) == "before"
    assert _read_value(target) == "restored"


def test_restore_refuses_corrupt_backup(tmp_path):
    corrupt = tmp_path / "corrupt.db"
    target = tmp_path / "target.db"

    corrupt.write_bytes(b"not a sqlite database")

    with pytest.raises((sqlite3.DatabaseError, RuntimeError)):
        restore_database(corrupt, target)

    assert not target.exists()


def test_unicode_and_spaces_in_paths(tmp_path):
    root = tmp_path / "данни с интервали"
    root.mkdir()

    source = root / "източник база.db"
    backup_dir = root / "резервни копия"
    target = root / "възстановена база.db"

    _create_database(source, "unicode-ok")

    backup = create_backup(source, backup_dir)
    restore_database(backup, target)

    assert _read_value(target) == "unicode-ok"


def test_backup_retention_removes_old_matching_backups(tmp_path):
    source = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    _create_database(source, "current")

    old_backup = backup_dir / "source-20000101-000000.db"
    _create_database(old_backup, "old")

    import os
    import time

    old_time = time.time() - (20 * 24 * 60 * 60)
    os.utime(old_backup, (old_time, old_time))

    create_backup(source, backup_dir, retention_days=14)

    assert not old_backup.exists()


def test_backup_retention_keeps_recent_matching_backups(tmp_path):
    source = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    _create_database(source, "current")

    recent_backup = backup_dir / "source-20000101-000000.db"
    _create_database(recent_backup, "recent")

    import os
    import time

    recent_time = time.time() - (10 * 24 * 60 * 60)
    os.utime(recent_backup, (recent_time, recent_time))

    create_backup(source, backup_dir, retention_days=14)

    assert recent_backup.exists()
