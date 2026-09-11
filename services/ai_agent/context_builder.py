from __future__ import annotations

from pathlib import Path

from .adapters import (
    DEFAULT_DB_PATH,
    DEFAULT_SERVICE_REQUESTS_PATH,
    load_professional_application,
    load_professional_calendar_conflicts,
    load_professional_review_summary,
    load_professional_workload,
    load_professionals,
    load_property,
    load_service_request,
)
from .agent import (
    ProfessionalContext,
    PropertyContext,
    RecommendationContext,
    ServiceRequestContext,
)


def _normalize_optional_bool(value: object) -> bool | None:
    if value is True:
        return True

    if value is False:
        return False

    if value is None:
        return None

    text = str(value).strip().casefold()

    if text in {"true", "1", "yes", "y", "on"}:
        return True

    if text in {"false", "0", "no", "n", "off"}:
        return False

    return None


def _split_service_categories(value: str) -> tuple[str, ...]:
    if not value:
        return ()

    return tuple(
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    )


def build_recommendation_context(
    request_id: str,
    *,
    organization_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    service_requests_path: Path = DEFAULT_SERVICE_REQUESTS_PATH,
    professional_applications_path: Path = Path("data/professional_applications.jsonl"),
) -> RecommendationContext | None:
    request_record = load_service_request(
        request_id,
        path=service_requests_path,
    )

    if not request_record:
        return None

    request_organization_id = str(
        request_record.get("organization_id", "")
    ).strip()

    effective_org = (
        str(organization_id).strip()
        if organization_id
        else request_organization_id or None
    )

    if not effective_org:
        return None

    property_id = str(
        request_record.get("property_id", "")
    ).strip()

    property_record = None

    if property_id:
        property_record = load_property(
            property_id,
            organization_id=effective_org,
            db_path=db_path,
        )

    property_location = None

    if property_record:
        property_location = str(
            property_record.get("location", "")
        ).strip() or None
    else:
        property_location = str(
            request_record.get("property_city", "")
        ).strip() or None

    service_request = ServiceRequestContext(
        request_id=str(request_record.get("id", "")).strip(),
        category=str(
            request_record.get("category", "")
            or request_record.get("service_category", "")
        ).strip(),
        description=str(
            request_record.get("description", "")
            or request_record.get("notes", "")
        ).strip(),
        urgency=str(
            request_record.get("urgency", "")
        ).strip() or None,
        preferred_date=str(
            request_record.get("preferred_date", "")
        ).strip() or None,
    )

    property_context = PropertyContext(
        property_id=property_id or "unknown",
        location=property_location,
    )

    professionals = []

    for professional_record in load_professionals(
        organization_id=effective_org,
        db_path=db_path,
    ):
        professional_id = str(
            professional_record.get("id", "")
        ).strip()

        review_summary = load_professional_review_summary(
            professional_id,
            db_path=db_path,
        )

        workload = load_professional_workload(
            professional_id,
            organization_id=effective_org,
            db_path=db_path,
        )

        calendar_conflicts = load_professional_calendar_conflicts(
            professional_id,
            service_request.preferred_date,
            organization_id=effective_org,
            db_path=db_path,
        )

        application = load_professional_application(
            professional_id,
            path=professional_applications_path,
        )

        available_for_requests = None
        professional_location = None

        if application:
            available_for_requests = _normalize_optional_bool(
                application.get("available_for_requests")
            )

            professional_location = str(
                application.get("city", "")
            ).strip() or None

        professionals.append(
            ProfessionalContext(
                professional_id=professional_id,
                name=str(
                    professional_record.get("full_name", "")
                ).strip(),
                service_categories=_split_service_categories(
                    professional_record.get(
                        "service_categories",
                        "",
                    )
                ),
                account_status=str(
                    professional_record.get("status", "")
                ).strip(),
                available_for_requests=available_for_requests,
                location=professional_location,
                known_calendar_conflicts=calendar_conflicts,
                workload=workload,
                average_rating=review_summary["average_rating"],
                review_count=review_summary["review_count"],
                reliability_score=None,
            )
        )

    return RecommendationContext(
        service_request=service_request,
        property=property_context,
        professionals=tuple(professionals),
    )
