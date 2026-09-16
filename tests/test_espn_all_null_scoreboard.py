"""Regression tests for temporary ESPN soccer/all scoreboard failures."""

from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider
from custom_components.teamtracker.provide_espn_all_supplemented import (
    SupplementalEspnAllLeaguesProvider,
)
from custom_components.teamtracker.provider_factory import get_provider


def test_factory_routes_config_lookup_to_espn_all_and_runtime_to_supplemental():
    config_provider = get_provider("soccer", "all")
    runtime_provider = get_provider("soccer", "all", "605")

    assert type(config_provider) is EspnAllLeaguesProvider
    assert type(runtime_provider) is SupplementalEspnAllLeaguesProvider


def test_null_scoreboard_payload_becomes_empty_mapping():
    response = EspnAllLeaguesProvider._normalize_scoreboard_response(
        {
            "data": None,
            "url": "https://example.invalid/scoreboard",
            "timestamp": "now",
        }
    )

    assert response["data"] == {}
    assert response["url"] == "https://example.invalid/scoreboard"
    assert response["timestamp"] == "now"


def test_valid_scoreboard_payload_is_preserved():
    source = {
        "data": {"events": [{"id": "1"}]},
        "url": "u",
        "timestamp": "t",
    }

    response = EspnAllLeaguesProvider._normalize_scoreboard_response(source)

    assert response == source
    assert response is not source
