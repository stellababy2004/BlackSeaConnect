"""Canonical service taxonomy for AI recommendation matching.

Only explicit, deterministic aliases belong here.
Do not use fuzzy matching or LLM interpretation for eligibility decisions.
"""

from __future__ import annotations


SERVICE_CATEGORY_ALIASES: dict[str, str] = {
    # Cleaning
    "cleaning": "cleaning",
    "\u043f\u043e\u0447\u0438\u0441\u0442\u0432\u0430\u043d\u0435": "cleaning",
    "nettoyage": "cleaning",
    "\u0443\u0431\u043e\u0440\u043a\u0430": "cleaning",

    # Maintenance
    "maintenance": "maintenance",
    "\u043f\u043e\u0434\u0434\u0440\u044a\u0436\u043a\u0430": "maintenance",
    "entretien": "maintenance",
    "\u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u043e\u0431\u0441\u043b\u0443\u0436\u0438\u0432\u0430\u043d\u0438\u0435": "maintenance",

    # Inspection
    "inspection": "inspection",
    "\u0438\u043d\u0441\u043f\u0435\u043a\u0446\u0438\u044f": "inspection",
    "inspection du bien": "inspection",
    "\u043e\u0441\u043c\u043e\u0442\u0440": "inspection",

    # Concierge
    "concierge support": "concierge",
    "concierge": "concierge",
    "\u043a\u043e\u043d\u0441\u0438\u0435\u0440\u0436": "concierge",
    "\u043a\u043e\u043d\u0441\u0438\u0435\u0440\u0436 \u0443\u0441\u043b\u0443\u0433\u0438": "concierge",
    "conciergerie": "concierge",
    "service de conciergerie": "concierge",
    "\u043a\u043e\u043d\u0441\u044c\u0435\u0440\u0436": "concierge",
    "\u043a\u043e\u043d\u0441\u044c\u0435\u0440\u0436-\u0441\u0435\u0440\u0432\u0438\u0441": "concierge",

    # Airport transfer
    "airport transfer": "airport_transfer",
    "\u043b\u0435\u0442\u0438\u0449\u0435\u043d \u0442\u0440\u0430\u043d\u0441\u0444\u0435\u0440": "airport_transfer",
    "transfert a\u00e9roport": "airport_transfer",
    "transfert depuis l\u2019a\u00e9roport": "airport_transfer",
    "\u0442\u0440\u0430\u043d\u0441\u0444\u0435\u0440 \u0438\u0437 \u0430\u044d\u0440\u043e\u043f\u043e\u0440\u0442\u0430": "airport_transfer",

    # Hospitality consultant
    "hospitality consultant": "hospitality_consultant",
    "\u043a\u043e\u043d\u0441\u0443\u043b\u0442\u0430\u043d\u0442 \u043f\u043e \u0433\u043e\u0441\u0442\u043e\u043f\u0440\u0438\u0435\u043c\u0441\u0442\u0432\u043e": "hospitality_consultant",
    "consultant en hospitalit\u00e9": "hospitality_consultant",
    "\u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u043d\u0442 \u043f\u043e \u0433\u043e\u0441\u0442\u0435\u043f\u0440\u0438\u0438\u043c\u0441\u0442\u0432\u0443": "hospitality_consultant",
}


def normalize_service_category(value: str | None) -> str | None:
    text = str(value or "").strip().casefold()

    if not text:
        return None

    return SERVICE_CATEGORY_ALIASES.get(text)


def categories_match(
    request_category: str | None,
    professional_categories: tuple[str, ...],
) -> bool:
    request_normalized = normalize_service_category(request_category)

    if request_normalized is None:
        return False

    professional_normalized = {
        normalized
        for category in professional_categories
        if (normalized := normalize_service_category(category)) is not None
    }

    return request_normalized in professional_normalized
