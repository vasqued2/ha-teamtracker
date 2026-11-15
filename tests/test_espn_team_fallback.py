"""Regression tests for ESPN team fallback after a missing scoreboard payload."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.teamtracker.provide_espn import EspnProvider


def _provider(scoreboard: dict, team: dict) -> EspnProvider:
    provider = EspnProvider()
    provider._coordinator = SimpleNamespace(
        hass=object(), team_id="TEST", team_number="100", get_lang=lambda: "en"
    )
    provider.async_get_scoreboard_data = AsyncMock(return_value=scoreboard)
    provider.async_get_teams_teamnumber_data = AsyncMock(return_value=team)
    return provider


def _team_response() -> dict:
    return {
        "data": {
            "team": {
                "nextEvent": [{"competitions": [{"competitors": [{"id": "100"}]}]}]
            }
        },
        "url": "https://example.invalid/teams/100",
        "timestamp": "team-timestamp",
    }


@pytest.mark.parametrize("payload", [None, {}, [], "unavailable"])
async def test_valid_team_fallback_without_scoreboard_metadata(payload):
    scoreboard = {"data": payload, "url": "scoreboard", "timestamp": "scoreboard-time"}
    team = _team_response()
    provider = _provider(scoreboard, team)

    result = await provider.async_update_sport_data()

    assert result is team
    assert "leagues" not in result["data"]
    provider.async_get_teams_teamnumber_data.assert_awaited_once()


async def test_team_fallback_preserves_available_league_metadata():
    leagues = [{"id": "test-league", "name": "Test League"}]
    scoreboard = {"data": {"events": [], "leagues": leagues}}
    team = _team_response()
    provider = _provider(scoreboard, team)

    result = await provider.async_update_sport_data()

    assert result is team
    assert result["data"]["leagues"] == leagues
    assert result["url"] == "https://example.invalid/teams/100"
    assert result["timestamp"] == "team-timestamp"


@pytest.mark.parametrize("team_data", [None, {"team": {"nextEvent": []}}])
async def test_unsuccessful_team_fallback_preserves_original_response(team_data):
    scoreboard = {"data": None, "url": "scoreboard", "timestamp": "scoreboard-time"}
    provider = _provider(scoreboard, {"data": team_data})

    assert await provider.async_update_sport_data() is scoreboard


async def test_scoreboard_match_does_not_call_team_fallback():
    scoreboard = {
        "data": {
            "events": [
                {
                    "competitions": [
                        {"competitors": [{"team": {"abbreviation": "TEST"}}]}
                    ]
                }
            ]
        }
    }
    provider = _provider(scoreboard, _team_response())

    assert await provider.async_update_sport_data() is scoreboard
    provider.async_get_teams_teamnumber_data.assert_not_awaited()
