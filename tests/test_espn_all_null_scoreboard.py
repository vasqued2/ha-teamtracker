"""Regression tests for temporary ESPN soccer/all scoreboard failures."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider
from custom_components.teamtracker.provide_espn_all_resilient import (
    ResilientEspnAllLeaguesProvider,
)
from custom_components.teamtracker.provider_factory import get_provider


def test_factory_limits_resilient_wrapper_to_soccer_all():
    soccer = get_provider("soccer", "all", "605")
    basketball = get_provider("basketball", "all", "1")

    assert isinstance(soccer, ResilientEspnAllLeaguesProvider)
    assert type(basketball) is EspnAllLeaguesProvider


@pytest.mark.asyncio
async def test_null_scoreboard_payload_becomes_empty_mapping():
    provider = ResilientEspnAllLeaguesProvider()

    with patch.object(
        EspnAllLeaguesProvider,
        "async_call_espn_api",
        new=AsyncMock(
            return_value={
                "data": None,
                "url": "https://example.invalid/scoreboard",
                "timestamp": "now",
            }
        ),
    ):
        response = await provider.async_call_espn_api(
            None,
            "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard",
            {},
            "PAOK",
            "605",
        )

    assert response["data"] == {}
    assert response["url"] == "https://example.invalid/scoreboard"
    assert response["timestamp"] == "now"


@pytest.mark.asyncio
async def test_non_scoreboard_null_payload_is_not_changed():
    provider = ResilientEspnAllLeaguesProvider()

    with patch.object(
        EspnAllLeaguesProvider,
        "async_call_espn_api",
        new=AsyncMock(return_value={"data": None, "url": "u", "timestamp": "t"}),
    ):
        response = await provider.async_call_espn_api(
            None,
            "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/605",
            {},
            "PAOK",
            "605",
        )

    assert response == {"data": None, "url": "u", "timestamp": "t"}
