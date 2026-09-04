"""Regression tests for the isolated ESPN ALL team-schedule fallback."""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider


def _event(event_id: str, event_date: date, team_id: str = "435") -> dict:
    return {
        "id": event_id,
        "date": f"{event_date.isoformat()}T16:00Z",
        "name": "Olympiacos at Volos NFC",
        "shortName": "OLY @ VOL",
        "status": {"type": {"state": "pre", "completed": False}},
        "competitions": [
            {
                "id": event_id,
                "date": f"{event_date.isoformat()}T16:00Z",
                "status": {"type": {"state": "pre", "completed": False}},
                "competitors": [
                    {
                        "id": "20043",
                        "type": "team",
                        "team": {
                            "id": "20043",
                            "abbreviation": "VOL",
                            "displayName": "Volos NFC",
                        },
                    },
                    {
                        "id": team_id,
                        "type": "team",
                        "team": {
                            "id": team_id,
                            "abbreviation": "OLY",
                            "displayName": "Olympiacos",
                        },
                    },
                ],
            }
        ],
    }


def test_schedule_response_for_dates_filters_without_mutating_cache():
    today = date.today()
    wanted = _event("401896768", today + timedelta(days=1))
    later = _event("401896762", today + timedelta(days=8))
    cached = {
        "data": {"events": [wanted, later]},
        "url": "team-schedule",
        "timestamp": None,
    }

    result = EspnAllLeaguesProvider._schedule_response_for_dates(
        {"schedule_response": cached},
        f"{today.strftime('%Y%m%d')}-"
        f"{(today + timedelta(days=1)).strftime('%Y%m%d')}",
    )

    assert [event["id"] for event in result["data"]["events"]] == ["401896768"]
    assert len(cached["data"]["events"]) == 2


@pytest.mark.asyncio
async def test_all_provider_uses_schedule_when_native_all_omits_team():
    today = date.today()
    next_game = today + timedelta(days=1)
    schedule_response = {
        "data": {"events": [_event("401896768", next_game)]},
        "url": "team-schedule",
        "timestamp": None,
    }

    provider = object.__new__(EspnAllLeaguesProvider)
    provider.lookups = {
        "team_list": [],
        "derived_league_name": "Greek Super League",
    }
    provider._coordinator = SimpleNamespace(
        name="Olympiacos",
        sport_path="soccer",
        league_path="all",
        team_id="435",
    )
    provider._async_get_team_schedule = AsyncMock(
        return_value={
            "next_game_date": next_game,
            "derived_league_name": "Greek Super League",
            "expires": next_game,
            "schedule_response": schedule_response,
        }
    )
    provider.async_call_espn_api = AsyncMock(
        return_value={
            "data": {"events": []},
            "url": "all-scoreboard",
            "timestamp": None,
        }
    )

    result = await provider._async_fetch_scoreboard_data(None, "en")

    assert result["url"] == "team-schedule"
    assert [event["id"] for event in result["data"]["events"]] == ["401896768"]
    assert result["lookups"]["derived_league_name"] == "Greek Super League"
