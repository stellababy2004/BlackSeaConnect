from services.ai_agent.taxonomy import (
    categories_match,
    normalize_service_category,
)


def test_taxonomy_normalizes_case_and_whitespace():
    assert normalize_service_category(" Cleaning ") == "cleaning"
    assert normalize_service_category("MAINTENANCE") == "maintenance"


def test_taxonomy_concierge_alias_matches():
    assert categories_match(
        "Concierge",
        ("Concierge Support",),
    ) is True


def test_taxonomy_airport_transfer_does_not_match_concierge():
    assert categories_match(
        "Airport Transfer",
        ("Concierge Support",),
    ) is False


def test_taxonomy_unknown_category_does_not_match():
    assert normalize_service_category("Pool Technician") is None
    assert categories_match(
        "Pool Technician",
        ("Maintenance",),
    ) is False

def test_taxonomy_multilingual_cleaning_aliases_match():
    for request_value in (
        "Cleaning",
        "\u041f\u043e\u0447\u0438\u0441\u0442\u0432\u0430\u043d\u0435",
        "Nettoyage",
        "\u0423\u0431\u043e\u0440\u043a\u0430",
    ):
        assert categories_match(
            request_value,
            ("Cleaning",),
        ) is True


def test_taxonomy_multilingual_maintenance_aliases_match():
    for request_value in (
        "Maintenance",
        "\u041f\u043e\u0434\u0434\u0440\u044a\u0436\u043a\u0430",
        "Entretien",
        "\u0422\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u043e\u0431\u0441\u043b\u0443\u0436\u0438\u0432\u0430\u043d\u0438\u0435",
    ):
        assert categories_match(
            request_value,
            ("Maintenance",),
        ) is True


def test_taxonomy_multilingual_inspection_aliases_match():
    for request_value in (
        "Inspection",
        "\u0418\u043d\u0441\u043f\u0435\u043a\u0446\u0438\u044f",
        "Inspection du bien",
        "\u041e\u0441\u043c\u043e\u0442\u0440",
    ):
        assert categories_match(
            request_value,
            ("Inspection",),
        ) is True


def test_taxonomy_multilingual_concierge_aliases_match():
    for request_value in (
        "Concierge",
        "\u041a\u043e\u043d\u0441\u0438\u0435\u0440\u0436",
        "Conciergerie",
        "\u041a\u043e\u043d\u0441\u044c\u0435\u0440\u0436",
    ):
        assert categories_match(
            request_value,
            ("Concierge Support",),
        ) is True


def test_taxonomy_multilingual_airport_transfer_aliases_match():
    for request_value in (
        "Airport Transfer",
        "\u041b\u0435\u0442\u0438\u0449\u0435\u043d \u0442\u0440\u0430\u043d\u0441\u0444\u0435\u0440",
        "Transfert a\u00e9roport",
        "\u0422\u0440\u0430\u043d\u0441\u0444\u0435\u0440 \u0438\u0437 \u0430\u044d\u0440\u043e\u043f\u043e\u0440\u0442\u0430",
    ):
        assert categories_match(
            request_value,
            ("Airport Transfer",),
        ) is True


def test_taxonomy_multilingual_hospitality_consultant_aliases_match():
    for request_value in (
        "Hospitality Consultant",
        "\u041a\u043e\u043d\u0441\u0443\u043b\u0442\u0430\u043d\u0442 \u043f\u043e \u0433\u043e\u0441\u0442\u043e\u043f\u0440\u0438\u0435\u043c\u0441\u0442\u0432\u043e",
        "Consultant en hospitalit\u00e9",
        "\u041a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u043d\u0442 \u043f\u043e \u0433\u043e\u0441\u0442\u0435\u043f\u0440\u0438\u0438\u043c\u0441\u0442\u0432\u0443",
    ):
        assert categories_match(
            request_value,
            ("Hospitality Consultant",),
        ) is True


def test_taxonomy_multilingual_aliases_do_not_cross_match():
    assert categories_match(
        "\u041f\u043e\u0447\u0438\u0441\u0442\u0432\u0430\u043d\u0435",
        ("Maintenance",),
    ) is False

    assert categories_match(
        "Entretien",
        ("Cleaning",),
    ) is False

    assert categories_match(
        "\u0422\u0440\u0430\u043d\u0441\u0444\u0435\u0440 \u0438\u0437 \u0430\u044d\u0440\u043e\u043f\u043e\u0440\u0442\u0430",
        ("Concierge Support",),
    ) is False
