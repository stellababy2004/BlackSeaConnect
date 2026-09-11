from pathlib import Path
import json
import sqlite3

from services.ai_agent.adapters import (
    load_service_request,
    load_property,
    load_professionals,
    load_professional_review_summary,
)


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"

    conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE TABLE owner_properties (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            name TEXT NOT NULL,
            property_type TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE professional_accounts (
            email TEXT PRIMARY KEY,
            id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            full_name TEXT NOT NULL,
            company TEXT NOT NULL,
            service_categories TEXT NOT NULL,
            status TEXT NOT NULL,
            organization_id TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE owner_task_reviews (
            task_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            professional_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    return db_path


def test_load_service_request_returns_real_record(tmp_path):
    path = tmp_path / "service_requests.jsonl"

    record = {
        "id": "req-1",
        "owner_id": "owner-1",
        "service_category": "Cleaning",
    }

    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = load_service_request("req-1", path=path)

    assert result is not None
    assert result["id"] == "req-1"


def test_load_service_request_filters_demo_record(tmp_path):
    path = tmp_path / "service_requests.jsonl"

    record = {
        "id": "demo-request-1",
        "owner_id": "demo-owner-1",
        "service_category": "Cleaning",
    }

    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    assert load_service_request("demo-request-1", path=path) is None


def test_load_service_request_missing_returns_none(tmp_path):
    path = tmp_path / "service_requests.jsonl"
    path.write_text("", encoding="utf-8")

    assert load_service_request("missing", path=path) is None


def test_load_property_returns_matching_record(tmp_path):
    db_path = _make_db(tmp_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO owner_properties
        (id, owner_id, organization_id, name, property_type, location, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "prop-1",
            "owner-1",
            "org-1",
            "Apartment",
            "Apartment",
            "Sofia",
            "ACTIVE",
        ),
    )
    conn.commit()
    conn.close()

    result = load_property(
        "prop-1",
        organization_id="org-1",
        db_path=db_path,
    )

    assert result is not None
    assert result["location"] == "Sofia"


def test_load_property_respects_organization_scope(tmp_path):
    db_path = _make_db(tmp_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO owner_properties
        (id, owner_id, organization_id, name, property_type, location, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "prop-1",
            "owner-1",
            "org-1",
            "Apartment",
            "Apartment",
            "Sofia",
            "ACTIVE",
        ),
    )
    conn.commit()
    conn.close()

    result = load_property(
        "prop-1",
        organization_id="org-2",
        db_path=db_path,
    )

    assert result is None


def test_load_professionals_filters_demo_and_scopes_org(tmp_path):
    db_path = _make_db(tmp_path)

    conn = sqlite3.connect(db_path)

    conn.executemany(
        """
        INSERT INTO professional_accounts
        (
            email,
            id,
            created_at,
            full_name,
            company,
            service_categories,
            status,
            organization_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "real@example.com",
                "pro-1",
                "2026-01-01T00:00:00Z",
                "Real Pro",
                "",
                "Cleaning",
                "APPROVED",
                "org-1",
            ),
            (
                "demo.professional@example.test",
                "demo-pro-1",
                "2026-01-01T00:00:00Z",
                "Demo Pro",
                "",
                "Cleaning",
                "ACTIVE",
                "org-1",
            ),
            (
                "other@example.com",
                "pro-2",
                "2026-01-01T00:00:00Z",
                "Other Org",
                "",
                "Cleaning",
                "ACTIVE",
                "org-2",
            ),
        ],
    )

    conn.commit()
    conn.close()

    result = load_professionals(
        organization_id="org-1",
        db_path=db_path,
    )

    assert len(result) == 1
    assert result[0]["id"] == "pro-1"


def test_review_summary_no_reviews_is_neutral(tmp_path):
    db_path = _make_db(tmp_path)

    result = load_professional_review_summary(
        "pro-1",
        db_path=db_path,
    )

    assert result["average_rating"] is None
    assert result["review_count"] == 0


def test_review_summary_returns_average_and_count(tmp_path):
    db_path = _make_db(tmp_path)

    conn = sqlite3.connect(db_path)

    conn.executemany(
        """
        INSERT INTO owner_task_reviews
        (task_id, owner_id, professional_id, rating, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "task-1",
                "owner-1",
                "pro-1",
                5,
                "Excellent",
                "2026-01-01T00:00:00Z",
            ),
            (
                "task-2",
                "owner-2",
                "pro-1",
                3,
                "Okay",
                "2026-01-02T00:00:00Z",
            ),
        ],
    )

    conn.commit()
    conn.close()

    result = load_professional_review_summary(
        "pro-1",
        db_path=db_path,
    )

    assert result["average_rating"] == 4.0
    assert result["review_count"] == 2
from pathlib import Path
import json
import sqlite3

from services.ai_agent.context_builder import build_recommendation_context


def test_context_builder_uses_real_operational_data(tmp_path):
    db_path = tmp_path / "test.db"
    requests_path = tmp_path / "service_requests.jsonl"
    applications_path = Path("data/professional_applications.jsonl")

    conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE TABLE owner_properties (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            name TEXT NOT NULL,
            property_type TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE professional_accounts (
            email TEXT PRIMARY KEY,
            id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            full_name TEXT NOT NULL,
            company TEXT NOT NULL,
            service_categories TEXT NOT NULL,
            status TEXT NOT NULL,
            organization_id TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE owner_task_reviews (
            task_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            professional_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE operations_tasks (
            request_id TEXT PRIMARY KEY,
            id TEXT NOT NULL,
            assigned_professional_id TEXT NOT NULL,
            status TEXT NOT NULL,
            organization_id TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE calendar_events (
            id TEXT PRIMARY KEY,
            operation_task_id TEXT NOT NULL,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            status TEXT NOT NULL,
            organization_id TEXT NOT NULL
        )
    """)

    conn.execute("""
        INSERT INTO professional_accounts
        (
            email,
            id,
            created_at,
            full_name,
            company,
            service_categories,
            status,
            organization_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "pro@example.com",
        "pro-1",
        "2026-01-01T00:00:00Z",
        "Test Pro",
        "",
        "Cleaning",
        "APPROVED",
        "org-1",
    ))

    for i in range(3):
        conn.execute("""
            INSERT INTO operations_tasks
            (
                request_id,
                id,
                assigned_professional_id,
                status,
                organization_id
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            f"task-{i}",
            f"task-{i}",
            "pro-1",
            "ASSIGNED",
            "org-1",
        ))

    conn.execute("""
        INSERT INTO calendar_events
        (
            id,
            operation_task_id,
            start_datetime,
            end_datetime,
            status,
            organization_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "event-1",
        "task-0",
        "2026-06-24T10:00:00+00:00",
        "2026-06-24T11:00:00+00:00",
        "ASSIGNED",
        "org-1",
    ))

    conn.commit()
    conn.close()

    requests_path.write_text(
        json.dumps({
            "id": "req-1",
            "owner_id": "owner-1",
            "organization_id": "org-1",
            "service_category": "Cleaning",
            "preferred_date": "2026-06-24",
            "property_city": "Varna",
            "description": "Cleaning needed",
        }) + "\n",
        encoding="utf-8",
    )

    context = build_recommendation_context(
        "req-1",
        organization_id="org-1",
        db_path=db_path,
        service_requests_path=requests_path,
    )

    assert context is not None
    assert len(context.professionals) == 1

    pro = context.professionals[0]

    assert pro.workload == 3
    assert pro.known_calendar_conflicts == 1
from pathlib import Path
import json


def test_context_builder_fails_closed_without_organization(tmp_path):
    from services.ai_agent.context_builder import build_recommendation_context

    requests_path = tmp_path / "service_requests.jsonl"

    requests_path.write_text(
        json.dumps({
            "id": "req-no-org",
            "owner_id": "owner-1",
            "service_category": "Cleaning",
            "preferred_date": "2026-09-20",
            "property_city": "Varna",
            "description": "Cleaning needed",
        }) + "`n",
        encoding="utf-8",
    )

    context = build_recommendation_context(
        "req-no-org",
        db_path=tmp_path / "database-does-not-need-to-exist.db",
        service_requests_path=requests_path,
        professional_applications_path=tmp_path / "applications.jsonl",
    )

    assert context is None
from services.ai_agent.adapters import _is_demo_value


def test_demo_filter_detects_suffix_demo_ids():
    assert _is_demo_value("owner-demo") is True
    assert _is_demo_value("professional_demo") is True
    assert _is_demo_value("demo-owner") is True
    assert _is_demo_value("owner-real") is False
from services.ai_agent.context_builder import _normalize_optional_bool


def test_optional_bool_normalization():
    assert _normalize_optional_bool(True) is True
    assert _normalize_optional_bool(False) is False
    assert _normalize_optional_bool("true") is True
    assert _normalize_optional_bool("TRUE") is True
    assert _normalize_optional_bool("1") is True
    assert _normalize_optional_bool("yes") is True
    assert _normalize_optional_bool("false") is False
    assert _normalize_optional_bool("0") is False
    assert _normalize_optional_bool("no") is False
    assert _normalize_optional_bool(None) is None
    assert _normalize_optional_bool("") is None
    assert _normalize_optional_bool("maybe") is None
