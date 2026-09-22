from pathlib import Path
import sqlite3
from datetime import datetime

import app


KEEP_BACKUPS = 14


def main():
    source = app._owner_db_path()

    if not source.is_file():
        raise SystemExit(f"Database not found: {source}")

    backup_dir = Path("backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = backup_dir / f"blacksea_owner-{stamp}.db"

    with sqlite3.connect(str(source)) as src:
        with sqlite3.connect(str(destination)) as dst:
            src.backup(dst)

    with sqlite3.connect(str(destination)) as check:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]

    if result != "ok":
        destination.unlink(missing_ok=True)
        raise SystemExit(f"Backup failed integrity check: {result}")

    backups = sorted(
        backup_dir.glob("blacksea_owner-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for old_backup in backups[KEEP_BACKUPS:]:
        old_backup.unlink()

    print("Backup created successfully")
    print("Source :", source)
    print("Backup :", destination)
    print("Check  :", result)
    print("Kept   :", min(len(backups), KEEP_BACKUPS))


if __name__ == "__main__":
    main()
