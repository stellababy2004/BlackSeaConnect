from services.ai_agent import (
    ProfessionalContext,
    PropertyContext,
    RecommendationContext,
    ServiceRequestContext,
    evaluate_professional,
    rank_professionals,
)

def make_context(professionals):
    return RecommendationContext(
        service_request=ServiceRequestContext(
            request_id="REQ-1",
            category="Cleaning",
            description="Apartment cleaning",
            urgency="normal",
            preferred_date="2026-09-12",
        ),
        property=PropertyContext(
            property_id="PROP-1",
            location="Sofia",
        ),
        professionals=tuple(professionals),
    )

def make_professional(
    professional_id="PRO-1",
    name="Test Pro",
    service_categories=("Cleaning",),
    account_status="active",
    available_for_requests=True,
    location="Sofia",
    known_calendar_conflicts=0,
    workload=0,
    average_rating=None,
    review_count=None,
    reliability_score=None,
):
    return ProfessionalContext(
        professional_id=professional_id,
        name=name,
        service_categories=service_categories,
        account_status=account_status,
        available_for_requests=available_for_requests,
        location=location,
        known_calendar_conflicts=known_calendar_conflicts,
        workload=workload,
        average_rating=average_rating,
        review_count=review_count,
        reliability_score=reliability_score,
    )

def test_matching_professional_is_eligible():
    p = make_professional()
    result = evaluate_professional(make_context([p]), p)
    assert result.eligible is True

def test_wrong_service_category_is_ineligible():
    p = make_professional(service_categories=("Plumbing",))
    result = evaluate_professional(make_context([p]), p)
    assert result.eligible is False

def test_inactive_professional_is_ineligible():
    p = make_professional(account_status="suspended")
    result = evaluate_professional(make_context([p]), p)
    assert result.eligible is False

def test_not_available_is_ineligible():
    p = make_professional(available_for_requests=False)
    result = evaluate_professional(make_context([p]), p)
    assert result.eligible is False

def test_missing_location_is_allowed_with_warning():
    p = make_professional(location=None)
    result = evaluate_professional(make_context([p]), p)
    assert result.eligible is True
    assert "location" in result.unknown_fields

def test_date_only_calendar_event_does_not_exclude_candidate():
    p = make_professional(known_calendar_conflicts=1)

    result = evaluate_professional(make_context([p]), p)

    assert result.eligible is True
    assert result.score > 0
    assert (
        "Calendar events exist on the preferred date, but an exact time conflict is not verified."
        in result.warnings
    )
    assert "Known calendar events on preferred date: 1 (-3)." in result.reasons


def test_date_only_calendar_penalty_is_capped():
    one_event = make_professional(
        professional_id="CAL-1",
        known_calendar_conflicts=1,
    )
    many_events = make_professional(
        professional_id="CAL-MANY",
        known_calendar_conflicts=10,
    )

    context = make_context([one_event, many_events])

    one_result = evaluate_professional(context, one_event)
    many_result = evaluate_professional(context, many_events)

    assert one_result.eligible is True
    assert many_result.eligible is True
    assert one_result.score > many_result.score
    assert "Known calendar events on preferred date: 10 (-9)." in many_result.reasons

def test_high_workload_reduces_score():
    low = make_professional(professional_id="LOW", workload=0)
    high = make_professional(professional_id="HIGH", workload=10)
    ctx = make_context([low, high])
    assert evaluate_professional(ctx, low).score > evaluate_professional(ctx, high).score

def test_no_reviews_not_ineligible():
    p = make_professional(average_rating=None, review_count=None)
    result = evaluate_professional(make_context([p]), p)
    assert result.eligible is True

def test_reliability_increases_score():
    a = make_professional(professional_id="A", reliability_score=50)
    b = make_professional(professional_id="B", reliability_score=90)
    ctx = make_context([a, b])
    assert evaluate_professional(ctx, b).score > evaluate_professional(ctx, a).score

def test_returns_maximum_three():
    pros = [make_professional(professional_id=f"P{i}") for i in range(5)]
    result = rank_professionals(make_context(pros))
    assert len(result) == 3

def test_returns_empty_when_none_valid():
    pros = [
        make_professional(professional_id="A", account_status="suspended"),
        make_professional(professional_id="B", available_for_requests=False),
    ]
    assert rank_professionals(make_context(pros)) == ()

def test_deterministic_order():
    a = make_professional(professional_id="A")
    b = make_professional(professional_id="B")
    result = rank_professionals(make_context([b, a]))
    assert result[0].professional_id == "A"

def test_different_location_is_allowed_with_penalty():
    p = make_professional(location="Plovdiv")
    result = evaluate_professional(make_context([p]), p)

    assert result.eligible is True
    assert result.score > 0
    assert result.warnings


def test_returns_only_one_valid_candidate():
    valid = make_professional(professional_id="VALID")
    invalid = make_professional(
        professional_id="INVALID",
        account_status="suspended",
    )
    result = rank_professionals(make_context([valid, invalid]))
    assert len(result) == 1
    assert result[0].professional_id == "VALID"


def test_returns_only_two_valid_candidates():
    p1 = make_professional(professional_id="P1")
    p2 = make_professional(professional_id="P2")
    p3 = make_professional(
        professional_id="P3",
        available_for_requests=False,
    )
    result = rank_professionals(make_context([p1, p2, p3]))
    assert len(result) == 2


def test_higher_score_ranks_first():
    strong = make_professional(
        professional_id="STRONG",
        workload=0,
        average_rating=5,
        review_count=10,
        reliability_score=90,
    )
    weak = make_professional(
        professional_id="WEAK",
        workload=5,
        average_rating=3,
        review_count=5,
        reliability_score=50,
    )
    result = rank_professionals(make_context([weak, strong]))
    assert result[0].professional_id == "STRONG"


def test_missing_optional_values_are_supported():
    p = make_professional(
        location=None,
        known_calendar_conflicts=None,
        workload=None,
        average_rating=None,
        review_count=None,
        reliability_score=None,
    )
    result = evaluate_professional(make_context([p]), p)
    assert result.eligible is True
    assert result.unknown_fields
    assert result.warnings


def test_duplicate_professional_ids_raise_error():
    import pytest

    p1 = make_professional(professional_id="DUP")
    p2 = make_professional(professional_id="dup")

    with pytest.raises(ValueError):
        make_context([p1, p2])



def test_end_to_end_ranking_returns_expected_top_three(tmp_path):
    import json
    import sqlite3

    from services.ai_agent.context_builder import build_recommendation_context
    from services.ai_agent.tools import rank_professionals

    db_path = tmp_path / "ai_test.db"
    requests_path = tmp_path / "service_requests.jsonl"
    applications_path = tmp_path / "professional_applications.jsonl"

    conn = sqlite3.connect(db_path)

    conn.executescript(
        """
        CREATE TABLE professional_accounts (
            email TEXT PRIMARY KEY,
            id TEXT,
            created_at TEXT,
            full_name TEXT,
            phone TEXT,
            company TEXT,
            service_categories TEXT,
            status TEXT,
            last_login_at TEXT,
            organization_id TEXT
        );

        CREATE TABLE operations_tasks (
            id TEXT,
            request_id TEXT,
            assigned_professional_id TEXT,
            status TEXT,
            organization_id TEXT
        );

        CREATE TABLE calendar_events (
            id TEXT PRIMARY KEY,
            operation_task_id TEXT,
            title TEXT,
            start_datetime TEXT,
            end_datetime TEXT,
            status TEXT,
            organization_id TEXT
        );

        CREATE TABLE owner_task_reviews (
            task_id TEXT PRIMARY KEY,
            owner_id TEXT,
            professional_id TEXT,
            rating REAL,
            comment TEXT,
            created_at TEXT
        );
        """
    )

    professionals = [
        (
            "pro-maint-1@test.local",
            "pro-maint-1",
            "2026-09-11T06:00:00+00:00",
            "Maintenance Alpha",
            "",
            "Alpha Services",
            "Maintenance",
            "APPROVED",
            None,
            "org-global",
        ),
        (
            "pro-maint-2@test.local",
            "pro-maint-2",
            "2026-09-11T06:00:00+00:00",
            "Maintenance Beta",
            "",
            "Beta Services",
            "Maintenance",
            "APPROVED",
            None,
            "org-global",
        ),
        (
            "pro-maint-3@test.local",
            "pro-maint-3",
            "2026-09-11T06:00:00+00:00",
            "Maintenance Gamma",
            "",
            "Gamma Services",
            "Maintenance",
            "APPROVED",
            None,
            "org-global",
        ),
    ]

    conn.executemany(
        """
        INSERT INTO professional_accounts (
            email,
            id,
            created_at,
            full_name,
            phone,
            company,
            service_categories,
            status,
            last_login_at,
            organization_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        professionals,
    )

    conn.execute(
        """
        INSERT INTO operations_tasks
        (id, request_id, assigned_professional_id, status, organization_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("task-alpha-1", "req-alpha-1", "pro-maint-1", "IN_PROGRESS", "org-global"),
    )

    for i in range(3):
        conn.execute(
            """
            INSERT INTO operations_tasks
            (id, request_id, assigned_professional_id, status, organization_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"task-beta-{i}",
                f"req-beta-{i}",
                "pro-maint-2",
                "ASSIGNED",
                "org-global",
            ),
        )

    reviews = [
        ("review-a1", "owner-1", "pro-maint-1", 5.0, "", "2026-09-01"),
        ("review-a2", "owner-2", "pro-maint-1", 5.0, "", "2026-09-02"),
        ("review-a3", "owner-3", "pro-maint-1", 5.0, "", "2026-09-03"),
        ("review-b1", "owner-4", "pro-maint-2", 4.0, "", "2026-09-04"),
        ("review-b2", "owner-5", "pro-maint-2", 4.0, "", "2026-09-05"),
    ]

    conn.executemany(
        """
        INSERT INTO owner_task_reviews (
            task_id,
            owner_id,
            professional_id,
            rating,
            comment,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        reviews,
    )

    conn.commit()
    conn.close()

    sveti_vlas_bg = "\u0421\u0432\u0435\u0442\u0438 \u0412\u043b\u0430\u0441"

    applications = [
        {
            "id": "pro-maint-1",
            "status": "qualified",
            "available_for_requests": True,
            "city": sveti_vlas_bg,
            "country": "Bulgaria",
            "professional_category": "Maintenance",
            "service_type": "Maintenance",
        },
        {
            "id": "pro-maint-2",
            "status": "qualified",
            "available_for_requests": True,
            "city": "Sveti Vlas",
            "country": "Bulgaria",
            "professional_category": "Maintenance",
            "service_type": "Maintenance",
        },
        {
            "id": "pro-maint-3",
            "status": "qualified",
            "available_for_requests": True,
            "city": sveti_vlas_bg,
            "country": "Bulgaria",
            "professional_category": "Maintenance",
            "service_type": "Maintenance",
        },
    ]

    with applications_path.open("w", encoding="utf-8") as fh:
        for record in applications:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    request = {
        "id": "e2e-maintenance-request",
        "owner_id": "real-test-owner",
        "owner_email": "owner@test.local",
        "organization_id": "org-global",
        "property_id": "",
        "property_name": "E2E Test Property",
        "property_city": "Sveti Vlas",
        "category": "Maintenance",
        "description": "Water is leaking under the kitchen sink.",
        "urgency": "High",
        "preferred_date": "2026-09-12",
        "status": "new",
    }

    requests_path.write_text(
        json.dumps(request, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    context = build_recommendation_context(
        "e2e-maintenance-request",
        organization_id="org-global",
        db_path=db_path,
        service_requests_path=requests_path,
        professional_applications_path=applications_path,
    )

    assert context is not None

    ranked = rank_professionals(context)

    assert [item.professional_id for item in ranked] == [
        "pro-maint-1",
        "pro-maint-3",
        "pro-maint-2",
    ]

    assert [item.score for item in ranked] == [
        84.0,
        80.0,
        76.0,
    ]

    assert all(item.eligible for item in ranked)

def test_location_alias_plovdiv_cyrillic_matches():
    professional = make_professional(
        service_categories=("Maintenance",),
        location="\u041f\u043b\u043e\u0432\u0434\u0438\u0432",
    )

    context = RecommendationContext(
        service_request=ServiceRequestContext(
            request_id="REQ-LOCATION-PLOVDIV",
            category="Maintenance",
        ),
        property=PropertyContext(
            property_id="PROP-LOCATION-PLOVDIV",
            location="Plovdiv",
        ),
        professionals=(professional,),
    )

    result = evaluate_professional(context, professional)

    assert result.eligible is True
    assert "Location matches (+10)." in result.reasons


def test_location_alias_sveti_vlas_cyrillic_matches():
    professional = make_professional(
        service_categories=("Maintenance",),
        location="\u0421\u0432\u0435\u0442\u0438 \u0412\u043b\u0430\u0441",
    )

    context = RecommendationContext(
        service_request=ServiceRequestContext(
            request_id="REQ-LOCATION-SV",
            category="Maintenance",
        ),
        property=PropertyContext(
            property_id="PROP-LOCATION-SV",
            location="Sveti Vlas",
        ),
        professionals=(professional,),
    )

    result = evaluate_professional(context, professional)

    assert result.eligible is True
    assert "Location matches (+10)." in result.reasons


def test_location_alias_nessebar_spelling_matches():
    professional = make_professional(
        service_categories=("Maintenance",),location="Nessebar")

    context = RecommendationContext(
        service_request=ServiceRequestContext(
            request_id="REQ-LOCATION-NESEBAR",
            category="Maintenance",
        ),
        property=PropertyContext(
            property_id="PROP-LOCATION-NESEBAR",
            location="\u041d\u0435\u0441\u0435\u0431\u044a\u0440",
        ),
        professionals=(professional,),
    )

    result = evaluate_professional(context, professional)

    assert result.eligible is True
    assert "Location matches (+10)." in result.reasons


def test_nearby_locations_do_not_become_exact_matches():
    professional = make_professional(
        service_categories=("Maintenance",),
        location="\u041d\u0435\u0441\u0435\u0431\u044a\u0440",
    )

    context = RecommendationContext(
        service_request=ServiceRequestContext(
            request_id="REQ-LOCATION-DIFFERENT",
            category="Maintenance",
        ),
        property=PropertyContext(
            property_id="PROP-LOCATION-DIFFERENT",
            location="\u0421\u043b\u044a\u043d\u0447\u0435\u0432 \u0431\u0440\u044f\u0433",
        ),
        professionals=(professional,),
    )

    result = evaluate_professional(context, professional)

    assert result.eligible is True
    assert "Location matches (+10)." not in result.reasons
    assert (
        "Location does not exactly match; service coverage requires human verification."
        in result.warnings
    )
