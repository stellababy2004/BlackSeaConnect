"""Immutable input/output contracts. No Flask, persistence, or provider access.

Callers must supply authorized, organization-scoped, non-demo data. This module
cannot establish authorization or verify the provenance of supplied facts.
Dates/urgency/descriptions are context only; no text or date inference occurs.
None denotes an unknown optional value, not zero or False.
"""

from dataclasses import dataclass
from math import isfinite


def _text(value, field, *, required=False):
    if value is None and not required:
        return
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{field} must be {'non-empty ' if required else ''}text")


def _number(value, field, *, maximum=None, integer=False, minimum=0):
    if value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or (integer and not isinstance(value, int))
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(f"Invalid {field}")


@dataclass(frozen=True)
class ServiceRequestContext:
    request_id: str
    category: str
    description: str = ""
    urgency: str | None = None
    preferred_date: str | None = None

    def __post_init__(self):
        _text(self.request_id, "request_id", required=True)
        _text(self.category, "category", required=True)
        _text(self.description, "description", required=False)
        _text(self.urgency, "urgency")
        _text(self.preferred_date, "preferred_date")


@dataclass(frozen=True)
class PropertyContext:
    property_id: str
    location: str | None = None

    def __post_init__(self):
        _text(self.property_id, "property_id", required=True)
        _text(self.location, "location")


@dataclass(frozen=True)
class ProfessionalContext:
    professional_id: str
    name: str
    service_categories: tuple[str, ...] = ()
    account_status: str | None = None
    available_for_requests: bool | None = None
    location: str | None = None
    known_calendar_conflicts: int | None = None
    workload: int | None = None
    average_rating: float | None = None
    review_count: int | None = None
    reliability_score: float | None = None

    def __post_init__(self):
        _text(self.professional_id, "professional_id", required=True)
        _text(self.name, "name", required=True)
        _text(self.location, "location")
        _text(self.account_status, "account_status")
        if not isinstance(self.service_categories, tuple):
            raise ValueError("service_categories must be a tuple")
        for category in self.service_categories:
            _text(category, "service_categories item", required=True)
        if self.available_for_requests is not None and type(self.available_for_requests) is not bool:
            raise ValueError("available_for_requests must be bool or None")
        _number(self.known_calendar_conflicts, "known_calendar_conflicts", integer=True)
        _number(self.workload, "workload", integer=True)
        _number(self.review_count, "review_count", integer=True)
        _number(self.average_rating, "average_rating", minimum=1, maximum=5)
        _number(self.reliability_score, "reliability_score", maximum=100)


@dataclass(frozen=True)
class RecommendationContext:
    service_request: ServiceRequestContext
    property: PropertyContext
    professionals: tuple[ProfessionalContext, ...] = ()

    def __post_init__(self):
        if not isinstance(self.service_request, ServiceRequestContext):
            raise ValueError("service_request must be ServiceRequestContext")
        if not isinstance(self.property, PropertyContext):
            raise ValueError("property must be PropertyContext")
        if not isinstance(self.professionals, tuple) or any(
            not isinstance(item, ProfessionalContext) for item in self.professionals
        ):
            raise ValueError("professionals must be a tuple of ProfessionalContext")
        ids = [item.professional_id.strip().casefold() for item in self.professionals]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate professional_id")


@dataclass(frozen=True)
class CandidateResult:
    professional_id: str
    score: float
    eligible: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    unknown_fields: tuple[str, ...]


def recommend_professionals(context: RecommendationContext) -> tuple[CandidateResult, ...]:
    """Return up to three eligible candidates; never assign or contact anyone."""
    from .tools import rank_professionals

    return rank_professionals(context)
