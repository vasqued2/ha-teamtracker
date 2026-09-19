"""Regression tests for truncated ESPN ALL POST -> PRE handoff."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

from freezegun import freeze_time
import pytest

from custom_components.teamtracker.const import API_LIMIT
from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider


def _event(
    event_id: str,
    event_date: str,
    *,
    state: str,
    completed: bool,
    team_id: str,
    opponent_id: str,
    team_score=None,
    opponent_score=None,
) -> dict:
    competitors = [
        {
            "id": team_id,
            "type": "team",
            "team": {
                "id": team_id,
                "abbreviation": "PAOK" if team_id == "605" else "TEAM",
                "displayName": "PAOK" if team_id == "605" else "Tracked Team",
            },
        },
        {
            "id": opponent_id,
            "type": "team",
            "team": {
                "id": opponent_id,
                "abbreviation": "OPP",
                "displayName": "Opponent",
            },
        },
    ]

    if team_score is not None:
        competitors[0]["score"] = team_score
    if opponent_score is not None:
        competitors[1]["score"] = opponent_score

    status = {
        "type": {
            "state": state,
            "completed": completed,
            "shortDetail": "FT" if completed else "Scheduled",
        }
    }

    return {
        "id": event_id,
        "date": event_date,
        "name": "Tracked Team vs Opponent",
        "shortName": "TEAM vs OPP",
        "season": {"displayName": "2026-27 Competition"},
        "status": status,
        "competitions": [
            {
                "id": event_id,
                "date": event_date,
                "status": status,
                "competitors": competitors,
            }
        ],
    }


def _unrelated_events(count: int, event_date: str) -> list[dict]:
    return [
        _event(
            f"other-{index}",
            event_date,
            state="pre",
            completed=False,
            team_id=str(10000 + index * 2),
            opponent_id=str(10001 + index * 2),
        )
        for index in range(count)
    ]


def _provider(team_id: str, schedule_info: dict) -> EspnAllLeaguesProvider:
    provider = object.__new__(EspnAllLeaguesProvider)
    provider.lookups = {"team_list": []}
    provider._coordinator = SimpleNamespace(
        name="Tracked Team",
        sport_path="soccer",
        league_path="all",
        team_id=team_id,
    )
    provider._async_get_team_schedule = AsyncMock(return_value=schedule_info)
    return provider


def _schedule_info(next_game_date: date, next_event: dict, schedule_events: list[dict]):
    return {
        "next_game_date": next_game_date,
        "derived_league_name": "Competition",
        "expires": next_game_date,
        "next_events": [next_event],
        "team_response": {
            "data": {"team": {"id": next_event["competitions"][0]["competitors"][0]["id"]}},
            "url": "team-metadata",
            "timestamp": "2026-09-14T05:30:00+00:00",
        },
        "schedule_response": {
            "data": {"events": schedule_events},
            "url": "team-schedule",
            "timestamp": "2026-09-14T05:30:00+00:00",
        },
    }


@pytest.mark.asyncio
async def test_truncated_all_handoff_keeps_recent_post_and_next_pre():
    """PAOK live case: API_LIMIT hides yesterday's POST from the ALL feed."""
    recent_post = _event(
        "paok-aris",
        "2026-09-13T18:00:00Z",
        state="post",
        completed=True,
        team_id="605",
        opponent_id="11553",
        team_score={"displayValue": "2", "value": 2.0},
        opponent_score={"displayValue": "0", "value": 0.0},
    )
    next_pre = _event(
        "paok-panetolikos",
        "2026-09-20T18:00:00Z",
        state="pre",
        completed=False,
        team_id="605",
        opponent_id="11431",
    )

    provider = _provider(
        "605",
        _schedule_info(date(2026, 9, 20), next_pre, [recent_post]),
    )
    provider.async_call_espn_api = AsyncMock(
        side_effect=[
            {
                "data": {"events": _unrelated_events(API_LIMIT, "2026-09-14T12:00:00Z")},
                "url": "all-scoreboard-broad",
                "timestamp": None,
            },
            {
                "data": {"events": [next_pre]},
                "url": "all-scoreboard-narrow",
                "timestamp": None,
            },
        ]
    )

    with freeze_time("2026-09-14T05:30:00Z"):
        result = await provider._async_fetch_scoreboard_data(None, "el")

    events = result["data"]["events"]
    assert [event["id"] for event in events] == [
        "paok-aris",
        "paok-panetolikos",
    ]
    post_competitors = events[0]["competitions"][0]["competitors"]
    assert post_competitors[0]["score"] == "2"
    assert post_competitors[1]["score"] == "0"


@pytest.mark.asyncio
async def test_truncated_all_handoff_does_not_restore_two_day_old_post():
    """Dortmund live case: an older POST must not replace the upcoming PRE."""
    old_post = _event(
        "dortmund-paderborn",
        "2026-09-12T18:00:00Z",
        state="post",
        completed=True,
        team_id="124",
        opponent_id="331",
        team_score={"displayValue": "3", "value": 3.0},
        opponent_score={"displayValue": "0", "value": 0.0},
    )
    next_pre = _event(
        "dortmund-stuttgart",
        "2026-09-19T16:30:00Z",
        state="pre",
        completed=False,
        team_id="124",
        opponent_id="134",
    )

    provider = _provider(
        "124",
        _schedule_info(date(2026, 9, 19), next_pre, [old_post]),
    )
    provider.async_call_espn_api = AsyncMock(
        side_effect=[
            {
                "data": {"events": _unrelated_events(API_LIMIT, "2026-09-14T12:00:00Z")},
                "url": "all-scoreboard-broad",
                "timestamp": None,
            },
            {
                "data": {"events": [next_pre]},
                "url": "all-scoreboard-narrow",
                "timestamp": None,
            },
        ]
    )

    with freeze_time("2026-09-14T05:30:00Z"):
        result = await provider._async_fetch_scoreboard_data(None, "de")

    assert [event["id"] for event in result["data"]["events"]] == [
        "dortmund-stuttgart"
    ]


@pytest.mark.asyncio
async def test_unsaturated_all_response_keeps_existing_narrow_retry_behavior():
    """The new handoff is limited to proven API_LIMIT truncation."""
    recent_post = _event(
        "recent-post",
        "2026-09-13T18:00:00Z",
        state="post",
        completed=True,
        team_id="605",
        opponent_id="11553",
    )
    next_pre = _event(
        "next-pre",
        "2026-09-20T18:00:00Z",
        state="pre",
        completed=False,
        team_id="605",
        opponent_id="11431",
    )

    provider = _provider(
        "605",
        _schedule_info(date(2026, 9, 20), next_pre, [recent_post]),
    )
    provider.async_call_espn_api = AsyncMock(
        side_effect=[
            {
                "data": {"events": _unrelated_events(API_LIMIT - 1, "2026-09-14T12:00:00Z")},
                "url": "all-scoreboard-broad",
                "timestamp": None,
            },
            {
                "data": {"events": [next_pre]},
                "url": "all-scoreboard-narrow",
                "timestamp": None,
            },
        ]
    )

    with freeze_time("2026-09-14T05:30:00Z"):
        result = await provider._async_fetch_scoreboard_data(None, "el")

    assert [event["id"] for event in result["data"]["events"]] == ["next-pre"]
