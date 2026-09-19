"""Regression tests keeping soccer/all team discovery out of runtime updates."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.teamtracker.provide_espn import EspnProvider
from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider


@pytest.mark.asyncio
async def test_runtime_soccer_all_team_fetch_delegates_to_original_endpoint():
    """The broad soccer league crawl is config-flow only."""
    hass = SimpleNamespace(data={})
    coordinator = SimpleNamespace(hass=hass)
    provider = EspnAllLeaguesProvider(coordinator)

    expected = {
        "data": [{"id": "605", "displayName": "PAOK"}],
        "url": "normal",
        "timestamp": "now",
    }

    with patch.object(
        EspnProvider,
        "_async_fetch_team_data",
        new=AsyncMock(return_value=expected),
    ) as original_fetch:
        response = await provider._async_fetch_team_data(
            hass,
            "soccer",
            "all",
            "PAOK",
        )

    assert response == expected
    original_fetch.assert_awaited_once_with(
        hass,
        "soccer",
        "all",
        "PAOK",
    )


@pytest.mark.asyncio
async def test_runtime_scoreboard_reuses_team_metadata_without_team_collection_call():
    """Runtime lookup metadata comes from the already-fetched team response."""
    hass = SimpleNamespace(data={})
    coordinator = SimpleNamespace(
        hass=hass,
        name="PAOK",
        sport_path="soccer",
        league_path="all",
        team_id="605",
        conference_id="",
        get_lang=lambda: "en",
    )
    provider = EspnAllLeaguesProvider(coordinator)

    provider._async_get_team_schedule = AsyncMock(
        return_value={
            "next_game_date": None,
            "team_response": {
                "data": {
                    "team": {
                        "id": "605",
                        "displayName": "PAOK Salonika",
                        "abbreviation": "PAOK",
                        "location": "Thessaloniki",
                        "logos": [{"href": "https://example.invalid/paok.png"}],
                    }
                },
                "url": "team",
                "timestamp": "now",
            },
            "next_events": [],
        }
    )
    provider.async_call_espn_api = AsyncMock(
        return_value={
            "data": {
                "events": [
                    {
                        "id": "1",
                        "date": "2026-09-16T17:00:00Z",
                        "competitions": [
                            {
                                "competitors": [
                                    {"team": {"id": "605"}},
                                    {"team": {"id": "999"}},
                                ]
                            }
                        ],
                    }
                ]
            },
            "url": "scoreboard",
            "timestamp": "now",
        }
    )
    provider.async_get_team_data = AsyncMock(
        side_effect=AssertionError("runtime must not crawl soccer team collections")
    )

    response = await provider._async_fetch_scoreboard_data(hass, "en")

    provider.async_get_team_data.assert_not_awaited()
    assert response["lookups"]["team_list"] == [
        {
            "id": "605",
            "displayName": "PAOK Salonika",
            "abbreviation": "PAOK",
            "location": "Thessaloniki",
            "logo": "https://example.invalid/paok.png",
        }
    ]
