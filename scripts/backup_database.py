from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _default_database_path() -> Path:
    value = str(os.getenv("DATABASE_PATH", "") or "").strip()
    if not value:
        raise ValueError("DATABASE_PATH is not configured and no source database path was provided.")
    return Path(value)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _integrity_check(database_path: Path) -> None:
    with sqlite3.connect(str(database_path), timeout=30) as connection:
        row = connection.execute("PRAGMA integrity_check;").fetchone()

    result = str(row[0] if row else "").strip().lower()
    if result != "ok":
        raise RuntimeError(f"SQLite integrity check failed for {database_path}")


def create_backup(source: Path, destination_dir: Path) -> Path:
    source = source.expanduser().resolve()
    destination_dir = destination_dir.expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Source database does not exist: {source}")

    destination_dir.mkdir(parents=True, exist_ok=True)

    backup_path = destination_dir / f"{source.stem}-{_timestamp()}.db"

    if backup_path.exists():
        raise FileExistsError(f"Backup already exists: {backup_path}")

    with sqlite3.connect(str(source), timeout=30) as source_connection:
        with sqlite3.connect(str(backup_path), timeout=30) as backup_connection:
            source_connection.backup(backup_connection)

    _integrity_check(backup_path)

    return backup_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and verify a SQLite database backup."
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Source SQLite database. Defaults to DATABASE_PATH.",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        required=True,
        help="Directory where the backup will be created.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        source = args.source if args.source is not None else _default_database_path()
        backup_path = create_backup(source, args.destination)
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(f"BACKUP FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"BACKUP OK: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
