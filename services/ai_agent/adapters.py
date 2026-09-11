"""Read-only data adapters for the BlackSea Connect AI recommendation agent.

This module intentionally does not import app.py and does not call any
schema, migration, synchronization, assignment, notification, email,
payment, or persistence helpers.

SQLite connections are opened with mode=ro.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("data/blacksea_owner.db")
DEFAULT_SERVICE_REQUESTS_PATH = Path("data/service_requests.jsonl")


def _readonly_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    uri = path.as_uri() + "?mode=ro"

    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row

    return connection


def _is_demo_value(value: Any) -> bool:
    text = str(value or "").strip().lower()

    return (
        text.startswith("demo-")
        or text.startswith("demo_")
        or text.endswith("-demo")
        or text.endswith("_demo")
        or text.endswith("@example.test")
        or text.endswith("@blackseaconnect.com") and "demo" in text
    )


def _is_demo_record(record: dict[str, Any]) -> bool:
    fields = (
        "id",
        "owner_id",
        "professional_id",
        "email",
        "owner_email",
    )

    return any(_is_demo_value(record.get(field)) for field in fields)


def load_service_request(
    request_id: str,
    *,
    path: Path = DEFAULT_SERVICE_REQUESTS_PATH,
) -> dict[str, Any] | None:
    target = str(request_id or "").strip()

    if not target:
        return None

    source = Path(path)

    if not source.exists():
        return None

    match = None

    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(record, dict):
                continue

            if str(record.get("id", "")).strip() == target:
                match = record

    if not match or _is_demo_record(match):
        return None

    return match


def load_property(
    property_id: str,
    *,
    organization_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any] | None:
    target = str(property_id or "").strip()

    if not target:
        return None

    query = """
        SELECT
            id,
            owner_id,
            organization_id,
            name,
            property_type,
            location,
            status
        FROM owner_properties
        WHERE id = ?
    """

    params: list[Any] = [target]

    if organization_id:
        query += " AND organization_id = ?"
        params.append(str(organization_id).strip())

    query += " LIMIT 1"

    with _readonly_connection(db_path) as connection:
        row = connection.execute(query, params).fetchone()

    if row is None:
        return None

    record = dict(row)

    if _is_demo_record(record):
        return None

    return record


def load_professionals(
    *,
    organization_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            id,
            email,
            full_name,
            company,
            service_categories,
            status,
            organization_id
        FROM professional_accounts
    """

    params: list[Any] = []

    if organization_id:
        query += " WHERE organization_id = ?"
        params.append(str(organization_id).strip())

    query += " ORDER BY created_at DESC, id DESC"

    with _readonly_connection(db_path) as connection:
        rows = connection.execute(query, params).fetchall()

    records = []

    for row in rows:
        record = dict(row)

        if _is_demo_record(record):
            continue

        records.append(record)

    return records


def load_professional_review_summary(
    professional_id: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    target = str(professional_id or "").strip()

    if not target:
        return {
            "average_rating": None,
            "review_count": 0,
        }

    with _readonly_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                AVG(rating) AS average_rating,
                COUNT(*) AS review_count
            FROM owner_task_reviews
            WHERE professional_id = ?
            """,
            (target,),
        ).fetchone()

    count = int(row["review_count"] or 0)

    return {
        "average_rating": (
            float(row["average_rating"])
            if count and row["average_rating"] is not None
            else None
        ),
        "review_count": count,
    }


def load_professional_application(
    professional_id: str,
    *,
    path: Path = Path("data/professional_applications.jsonl"),
) -> dict[str, Any] | None:
    target = str(professional_id or "").strip()

    if not target:
        return None

    source = Path(path)

    if not source.exists():
        return None

    match = None

    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(record, dict):
                continue

            if str(record.get("id", "")).strip() == target:
                match = record

    if not match or _is_demo_record(match):
        return None

    return {
        "id": str(match.get("id", "")).strip(),
        "status": str(match.get("status", "")).strip(),
        "available_for_requests": match.get("available_for_requests"),
        "city": str(match.get("city", "")).strip(),
        "country": str(match.get("country", "")).strip(),
        "professional_category": str(
            match.get("professional_category", "")
        ).strip(),
        "service_type": str(match.get("service_type", "")).strip(),
    }


def load_professional_workload(
    professional_id: str,
    *,
    organization_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> int | None:
    """Return the number of currently active tasks assigned to a professional.

    Only explicitly assigned operational tasks are counted.
    NEW, COMPLETED and ARCHIVED tasks are not considered active workload.
    """

    target = str(professional_id or "").strip()

    if not target:
        return None

    active_statuses = (
        "ASSIGNED",
        "ACCEPTED",
        "IN_PROGRESS",
        "WAITING_OWNER",
    )

    placeholders = ",".join("?" for _ in active_statuses)

    query = f"""
        SELECT COUNT(*) AS workload
        FROM operations_tasks
        WHERE assigned_professional_id = ?
          AND UPPER(TRIM(status)) IN ({placeholders})
    """

    params: list[Any] = [
        target,
        *active_statuses,
    ]

    if organization_id:
        query += " AND organization_id = ?"
        params.append(str(organization_id).strip())

    with _readonly_connection(db_path) as connection:
        row = connection.execute(query, params).fetchone()

    if row is None:
        return None

    return int(row["workload"] or 0)


def load_professional_calendar_conflicts(
    professional_id: str,
    preferred_date: str | None,
    *,
    organization_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> int | None:
    """Return known active calendar conflicts for the preferred date.

    Calendar events are linked to professionals through operations_tasks,
    using the stable assigned_professional_id rather than display names.
    """

    target = str(professional_id or "").strip()
    date_value = str(preferred_date or "").strip()

    if not target or not date_value:
        return None

    day_start = f"{date_value}T00:00:00"
    day_end = f"{date_value}T23:59:59"

    query = """
        SELECT COUNT(DISTINCT c.id) AS conflict_count
        FROM calendar_events c
        JOIN operations_tasks t
          ON (
              NULLIF(TRIM(c.operation_task_id), '') IS NOT NULL
              AND (
                  t.id = c.operation_task_id
                  OR t.request_id = c.operation_task_id
              )
          )
        WHERE t.assigned_professional_id = ?
          AND UPPER(TRIM(c.status)) NOT IN ('CANCELLED', 'COMPLETED')
          AND c.start_datetime <= ?
          AND c.end_datetime >= ?
    """

    params: list[Any] = [
        target,
        day_end,
        day_start,
    ]

    if organization_id:
        query += """
          AND c.organization_id = ?
          AND t.organization_id = ?
        """
        org = str(organization_id).strip()
        params.extend([org, org])

    with _readonly_connection(db_path) as connection:
        row = connection.execute(query, params).fetchone()

    if row is None:
        return None

    return int(row["conflict_count"] or 0)
