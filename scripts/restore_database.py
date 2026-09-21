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
        raise ValueError("DATABASE_PATH is not configured and no target database path was provided.")
    return Path(value)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _integrity_check(database_path: Path) -> None:
    with sqlite3.connect(str(database_path), timeout=30) as connection:
        row = connection.execute("PRAGMA integrity_check;").fetchone()

    result = str(row[0] if row else "").strip().lower()
    if result != "ok":
        raise RuntimeError(f"SQLite integrity check failed for {database_path}")


def restore_database(backup: Path, target: Path, force: bool = False) -> Path | None:
    backup = backup.expanduser().resolve()
    target = target.expanduser().resolve()

    if not backup.is_file():
        raise FileNotFoundError(f"Backup database does not exist: {backup}")

    _integrity_check(backup)

    safety_copy = None

    if target.exists():
        if not force:
            raise FileExistsError(
                f"Target database already exists: {target}. Use --force to overwrite it."
            )

        safety_copy = target.with_name(
            f"{target.stem}.pre-restore-{_timestamp()}{target.suffix}"
        )

        if safety_copy.exists():
            raise FileExistsError(f"Safety copy already exists: {safety_copy}")

        with sqlite3.connect(str(target), timeout=30) as source_connection:
            with sqlite3.connect(str(safety_copy), timeout=30) as safety_connection:
                source_connection.backup(safety_connection)

        _integrity_check(safety_copy)

    target.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(backup), timeout=30) as backup_connection:
        with sqlite3.connect(str(target), timeout=30) as target_connection:
            backup_connection.backup(target_connection)

    _integrity_check(target)

    return safety_copy


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify and restore a SQLite database backup."
    )
    parser.add_argument(
        "--backup",
        type=Path,
        required=True,
        help="SQLite backup file to restore.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        help="Target SQLite database. Defaults to DATABASE_PATH.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow replacing an existing target after creating a safety copy.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        target = args.target if args.target is not None else _default_database_path()
        safety_copy = restore_database(args.backup, target, force=args.force)
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(f"RESTORE FAILED: {exc}", file=sys.stderr)
        return 1

    if safety_copy:
        print(f"SAFETY COPY OK: {safety_copy}")

    print(f"RESTORE OK: {target.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
