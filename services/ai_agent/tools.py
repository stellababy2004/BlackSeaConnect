"""Pure business functions; these are not database or network tools.

Score (eligible only): 50 + 20 service match + 10 known location match
  - min(workload, 10) * 2
  + (average_rating - 3) * 5 * min(review_count / 5, 1)
  + (reliability_score - 50) / 10.
Unknown optional factors contribute zero. Ratings require a positive review
count. Scores are clamped to 0..100 and rounded to two decimal places.

Categories/locations use exact whitespace-normalized, case-insensitive labels.
No fuzzy matching, translation, geocoding, or broad service aliases are inferred.
Known calendar conflicts must describe the requested window; zero means no
known conflict, never a guarantee of availability. Missing window data is None.
"""

from .agent import CandidateResult, ProfessionalContext, RecommendationContext
from .taxonomy import categories_match


def _normalized(value):
    return " ".join((value or "").split()).casefold()


_LOCATION_ALIASES = {
    # Sofia
    "sofia": "sofia",
    "\u0441\u043e\u0444\u0438\u044f": "sofia",

    # Plovdiv
    "plovdiv": "plovdiv",
    "\u043f\u043b\u043e\u0432\u0434\u0438\u0432": "plovdiv",

    # Varna
    "varna": "varna",
    "\u0432\u0430\u0440\u043d\u0430": "varna",

    # Burgas
    "burgas": "burgas",
    "bourgas": "burgas",
    "\u0431\u0443\u0440\u0433\u0430\u0441": "burgas",

    # Sveti Vlas
    "sveti vlas": "sveti vlas",
    "st vlas": "sveti vlas",
    "saint vlas": "sveti vlas",
    "\u0441\u0432\u0435\u0442\u0438 \u0432\u043b\u0430\u0441": "sveti vlas",

    # Nessebar
    "nesebar": "nesebar",
    "nessebar": "nesebar",
    "\u043d\u0435\u0441\u0435\u0431\u044a\u0440": "nesebar",
    "\u043d\u0435\u0441\u0435\u0431\u0440": "nesebar",

    # Sunny Beach
    "sunny beach": "sunny beach",
    "\u0441\u043b\u044a\u043d\u0447\u0435\u0432 \u0431\u0440\u044f\u0433": "sunny beach",
    "\u0441\u043e\u043b\u043d\u0435\u0447\u043d\u044b\u0439 \u0431\u0435\u0440\u0435\u0433": "sunny beach",

    # Ravda
    "ravda": "ravda",
    "\u0440\u0430\u0432\u0434\u0430": "ravda",

    # Pomorie
    "pomorie": "pomorie",
    "\u043f\u043e\u043c\u043e\u0440\u0438\u0435": "pomorie",

    # Sozopol
    "sozopol": "sozopol",
    "\u0441\u043e\u0437\u043e\u043f\u043e\u043b": "sozopol",

    # Balchik
    "balchik": "balchik",
    "\u0431\u0430\u043b\u0447\u0438\u043a": "balchik",
}


def _normalize_location(value):
    normalized = _normalized(value)
    if not normalized:
        return ""
    return _LOCATION_ALIASES.get(normalized, normalized)


def evaluate_professional(
    context: RecommendationContext, professional: ProfessionalContext,
) -> CandidateResult:
    """Explain one candidate, including ineligible candidates (score zero)."""
    reasons, warnings, unknown = [], [], []
    eligible = True
    score = 50.0

    if not _normalized(professional.account_status):
        unknown.append("account_status")
    if _normalized(professional.account_status) not in {"approved", "active"}:
        eligible = False
        reasons.append("Account must be APPROVED or ACTIVE.")
    else:
        reasons.append("Account is approved or active.")

    if professional.available_for_requests is None:
        unknown.append("available_for_requests")
    if professional.available_for_requests is not True:
        eligible = False
        reasons.append("Availability for requests must be explicitly confirmed.")

    if not professional.service_categories:
        unknown.append("service_categories")

    if not categories_match(
        context.service_request.category,
        professional.service_categories,
    ):
        eligible = False
        reasons.append("No confirmed matching service category.")
    else:
        score += 20
        reasons.append("Service category matches (+20).")

    target = _normalize_location(context.property.location)
    location = _normalize_location(professional.location)
    if not target:
        unknown.append("property.location")
    if not location:
        unknown.append("location")
    if target and location:
        if target != location:
            score -= 5
            warnings.append(
                "Location does not exactly match; service coverage requires human verification."
            )
        else:
            score += 10
            reasons.append("Location matches (+10).")
    else:
        warnings.append("Location compatibility requires human verification.")

    conflicts = professional.known_calendar_conflicts
    if conflicts is None:
        unknown.append("known_calendar_conflicts")
        warnings.append("Calendar availability is unknown; verify the requested window.")
    elif conflicts > 0:
        calendar_penalty = min(conflicts, 3) * 3
        score -= calendar_penalty
        reasons.append(
            f"Known calendar events on preferred date: {conflicts} (-{calendar_penalty})."
        )
        warnings.append(
            "Calendar events exist on the preferred date, but an exact time conflict is not verified."
        )
    else:
        reasons.append("No known calendar conflict; availability is not guaranteed.")

    if professional.workload is None:
        unknown.append("workload")
    else:
        penalty = min(professional.workload, 10) * 2
        score -= penalty
        reasons.append(f"Known active workload: {professional.workload} (-{penalty}).")

    rating, count = professional.average_rating, professional.review_count
    if rating is None:
        unknown.append("average_rating")
    if count is None:
        unknown.append("review_count")
    if rating is not None and count is not None and count > 0:
        adjustment = (rating - 3) * 5 * min(count / 5, 1)
        score += adjustment
        reasons.append(f"Rating evidence: {rating:g}/5 from {count} reviews ({adjustment:+.2f}).")
    else:
        warnings.append("Insufficient review data; rating has a neutral contribution.")

    if professional.reliability_score is None:
        unknown.append("reliability_score")
    else:
        adjustment = (professional.reliability_score - 50) / 10
        score += adjustment
        reasons.append(f"Reliability contribution ({adjustment:+.2f}).")

    if unknown:
        warnings.append("Some input facts are unknown; human review is required.")
    return CandidateResult(
        professional.professional_id, round(max(0, min(100, score)), 2) if eligible else 0.0,
        eligible, tuple(reasons), tuple(warnings), tuple(unknown),
    )


def rank_professionals(context: RecommendationContext) -> tuple[CandidateResult, ...]:
    """Return 0..3 eligible candidates, descending score then canonical ID.

Rejected candidates are never used to fill the list. Use evaluate_professional
for their diagnostics. Inputs are immutable and remain unchanged.
"""
    candidates = (evaluate_professional(context, item) for item in context.professionals)
    return tuple(sorted(
        (item for item in candidates if item.eligible),
        key=lambda item: (-item.score, item.professional_id.strip().casefold()),
    )[:3])


# ---------------------------------------------------------------------------
# AI Operations Monitor
# ---------------------------------------------------------------------------

_OPERATIONS_MONITOR_BUCKET_ORDER = {
    "critical": 0,
    "needs_attention": 1,
    "waiting": 2,
    "ready_to_close": 3,
}

_OPERATIONS_MONITOR_SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "warning": 2,
    "low": 3,
    "info": 4,
}

_OPERATIONS_MONITOR_WAITING_CATEGORIES = {
    "owner_requests_waiting",
}

_OPERATIONS_MONITOR_READY_CATEGORIES = {
    "ready_to_close",
}


def build_operations_monitor(alerts) -> dict:
    """Build a deterministic, read-only operations attention summary.

    The caller supplies already-authorized operational alerts. This function
    performs no persistence, assignment, notification, email, payment, or
    status changes. Existing deterministic alert facts remain authoritative.
    """
    items = []

    for alert in alerts or ():
        if not isinstance(alert, dict):
            continue

        severity = str(alert.get("severity", "medium") or "medium").strip().lower()
        category = str(alert.get("category", "") or "").strip().lower()

        if category in _OPERATIONS_MONITOR_READY_CATEGORIES:
            bucket = "ready_to_close"
        elif category in _OPERATIONS_MONITOR_WAITING_CATEGORIES:
            bucket = "waiting"
        elif severity in {"critical", "high"}:
            bucket = "critical"
        else:
            bucket = "needs_attention"

        property_label = str(alert.get("property_label", "") or "").strip()
        operation_label = str(alert.get("operation_label", "") or "").strip()
        reservation_label = str(alert.get("reservation_label", "") or "").strip()
        detail = str(alert.get("detail", "") or "").strip()
        next_action = str(alert.get("recommended_action", "") or "").strip()
        link = str(alert.get("link", "") or "").strip()
        created_at = str(alert.get("created_at", "") or "").strip()

        reasons = tuple(
            value
            for value in (
                detail,
                f"Property: {property_label}" if property_label else "",
                f"Operation: {operation_label}" if operation_label else "",
                f"Reservation: {reservation_label}" if reservation_label else "",
            )
            if value
        )

        items.append({
            "bucket": bucket,
            "severity": severity,
            "category": category,
            "property_label": property_label,
            "operation_label": operation_label,
            "reservation_label": reservation_label,
            "created_at": created_at,
            "next_best_action": next_action,
            "reasons": reasons,
            "link": link,
        })

    items.sort(
        key=lambda item: (
            _OPERATIONS_MONITOR_BUCKET_ORDER.get(item["bucket"], 99),
            _OPERATIONS_MONITOR_SEVERITY_ORDER.get(item["severity"], 99),
            item["created_at"],
            item["property_label"].casefold(),
            item["operation_label"].casefold(),
        )
    )

    counts = {
        bucket: sum(1 for item in items if item["bucket"] == bucket)
        for bucket in _OPERATIONS_MONITOR_BUCKET_ORDER
    }

    attention_count = (
        counts["critical"]
        + counts["needs_attention"]
        + counts["waiting"]
    )

    return {
        "items": tuple(items),
        "counts": counts,
        "attention_count": attention_count,
        "has_attention": attention_count > 0,
    }
