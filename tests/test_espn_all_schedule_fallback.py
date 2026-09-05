"""Regression tests for the isolated ESPN ALL team-schedule fallback."""

import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from freezegun import freeze_time
import pytest

from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider

CAPTURES_DIR = "tests/tt/captures"


def _load_capture(filename: str) -> dict:
    with open(f"{CAPTURES_DIR}/{filename}", encoding="utf-8") as f:
        return json.load(f)


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


@pytest.mark.asyncio
async def test_paok_schedule_is_used_when_team_next_event_is_missing():
    """A missing /all team nextEvent must not hide a real scheduled fixture."""
    today = date.today()
    next_game = today + timedelta(days=2)

    schedule_response = {
        "data": {"events": [_event("401896765", next_game, team_id="605")]},
        "url": "team-schedule",
        "timestamp": None,
    }

    provider = object.__new__(EspnAllLeaguesProvider)
    provider.TEAM_SCHEDULE_KEY = "team-schedule-key"
    provider.instance_cache = {}
    provider.lookups = {"team_list": []}
    provider._coordinator = SimpleNamespace(
        name="PAOK",
        sport_path="soccer",
        league_path="all",
        team_id="605",
        hass=None,
    )

    provider.async_call_espn_api = AsyncMock(
        side_effect=[
            {
                "data": {"team": {"nextEvent": []}},
                "url": "team-info",
                "timestamp": None,
            },
            schedule_response,
            {
                "data": {"events": []},
                "url": "all-scoreboard-1",
                "timestamp": None,
            },
            {
                "data": {"events": []},
                "url": "all-scoreboard-2",
                "timestamp": None,
            },
        ]
    )

    result = await provider._async_fetch_scoreboard_data(None, "en")

    assert result["url"] == "team-schedule"
    assert [event["id"] for event in result["data"]["events"]] == ["401896765"]


@pytest.mark.asyncio
async def test_paok_uses_team_next_event_when_all_schedule_has_only_past_games():
    # Match the live PAOK failure: /all schedule is past-only, nextEvent is future.
    today = date.today()
    next_game = today + timedelta(days=2)
    past_game = today - timedelta(days=5)

    next_event = _event("401896765", next_game, team_id="605")
    past_event = _event("401896772", past_game, team_id="605")

    provider = object.__new__(EspnAllLeaguesProvider)
    provider.lookups = {
        "team_list": [],
        "derived_league_name": "Greek Super League",
    }
    provider._coordinator = SimpleNamespace(
        name="PAOK",
        sport_path="soccer",
        league_path="all",
        team_id="605",
    )
    provider._async_get_team_schedule = AsyncMock(
        return_value={
            "next_game_date": next_game,
            "derived_league_name": "Greek Super League",
            "expires": next_game,
            "next_events": [next_event],
            "schedule_response": {
                "data": {"events": [past_event]},
                "url": "team-schedule",
                "timestamp": None,
            },
        }
    )
    provider.async_call_espn_api = AsyncMock(
        return_value={
            "data": {"events": []},
            "url": "all-scoreboard",
            "timestamp": None,
        }
    )

    result = await provider._async_fetch_scoreboard_data(None, "el")

    assert [event["id"] for event in result["data"]["events"]] == ["401896765"]


@pytest.mark.asyncio
async def test_all_provider_uses_next_event_when_schedule_is_past_only():
    today = date.today()
    tracked_id = "9001"
    next_game = today + timedelta(days=2)
    past_game = today - timedelta(days=5)

    next_event = _event("future-next", next_game, team_id=tracked_id)
    past_event = _event("past-only", past_game, team_id=tracked_id)

    provider = object.__new__(EspnAllLeaguesProvider)
    provider.lookups = {"team_list": [], "derived_league_name": "Competition"}
    provider._coordinator = SimpleNamespace(
        name="Tracked Team",
        sport_path="soccer",
        league_path="all",
        team_id=tracked_id,
    )
    provider._async_get_team_schedule = AsyncMock(
        return_value={
            "next_game_date": next_game,
            "derived_league_name": "Competition",
            "expires": next_game,
            "next_events": [next_event],
            "team_response": {
                "data": {"team": {"id": tracked_id}},
                "url": "team-metadata",
                "timestamp": None,
            },
            "schedule_response": {
                "data": {"events": [past_event]},
                "url": "team-schedule",
                "timestamp": None,
            },
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

    assert result["url"] == "team-metadata"
    assert [event["id"] for event in result["data"]["events"]] == ["future-next"]


def _logo_fallback_event(event_date, team_a="9001", team_b="9002"):
    return {
        "id": "logo-event",
        "date": f"{event_date.isoformat()}T16:00Z",
        "competitions": [
            {
                "competitors": [
                    {
                        "id": team_a,
                        "team": {
                            "id": team_a,
                            "displayName": "Team A",
                            "logos": [
                                {"href": "https://example.invalid/team-a.svg"}
                            ],
                        },
                    },
                    {
                        "id": team_b,
                        "team": {
                            "id": team_b,
                            "displayName": "Team B",
                        },
                    },
                ]
            }
        ],
    }


def test_next_event_fallback_logo_parity_is_generic():
    today = date.today()
    event = _logo_fallback_event(today + timedelta(days=1))
    original_a = event["competitions"][0]["competitors"][0]["team"]
    original_b = event["competitions"][0]["competitors"][1]["team"]

    response = EspnAllLeaguesProvider._next_event_response_for_dates(
        {
            "sport_path": "soccer",
            "next_events": [event],
            "team_response": {
                "data": {},
                "url": "team-metadata",
                "timestamp": None,
            },
        },
        (
            f"{today.strftime('%Y%m%d')}-"
            f"{(today + timedelta(days=1)).strftime('%Y%m%d')}"
        ),
        {
            "data": {"events": []},
            "url": "all-scoreboard",
            "timestamp": None,
        },
    )

    teams = response["data"]["events"][0]["competitions"][0]["competitors"]
    assert teams[0]["team"]["logo"] == "https://example.invalid/team-a.svg"
    assert "logo" not in teams[1]["team"]
    assert "logo" not in original_a
    assert "logo" not in original_b


def test_next_event_logo_fallback_does_not_assume_soccer_for_other_sports():
    today = date.today()
    event = _logo_fallback_event(today + timedelta(days=1))

    response = EspnAllLeaguesProvider._next_event_response_for_dates(
        {
            "sport_path": "basketball",
            "next_events": [event],
            "team_response": {
                "data": {},
                "url": "team-metadata",
                "timestamp": None,
            },
        },
        (
            f"{today.strftime('%Y%m%d')}-"
            f"{(today + timedelta(days=1)).strftime('%Y%m%d')}"
        ),
        {
            "data": {"events": []},
            "url": "all-scoreboard",
            "timestamp": None,
        },
    )

    teams = response["data"]["events"][0]["competitions"][0]["competitors"]
    assert teams[0]["team"]["logo"] == "https://example.invalid/team-a.svg"
    assert "logo" not in teams[1]["team"]


@pytest.mark.asyncio
async def test_next_event_fallback_uses_selected_event_league_and_season():
    today = date.today()
    next_game = today + timedelta(days=1)
    tracked_id = "9001"

    event = _event("selected-event", next_game, team_id=tracked_id)
    event["season"] = {
        "year": 2026,
        "displayName": "2026-27 Selected Competition",
    }
    event["seasonType"] = {"name": "Regular Season"}

    for competitor in event["competitions"][0]["competitors"]:
        team = competitor["team"]
        team.pop("logo", None)
        team["logos"] = [
            {"href": "https://example.invalid/%s.png" % team["id"]}
        ]

    provider = object.__new__(EspnAllLeaguesProvider)
    provider.lookups = {
        "team_list": [],
        "derived_league_name": "Wrong Competition",
    }
    provider._coordinator = SimpleNamespace(
        name="Tracked Team",
        sport_path="soccer",
        league_path="all",
        team_id=tracked_id,
    )
    provider._async_get_team_schedule = AsyncMock(
        return_value={
            "next_game_date": next_game,
            "derived_league_name": "Wrong Competition",
            "expires": next_game,
            "next_events": [event],
            "team_response": {
                "data": {},
                "url": "team-metadata",
                "timestamp": None,
            },
            "schedule_response": {
                "data": {"events": []},
                "url": "team-schedule",
                "timestamp": None,
            },
        }
    )
    provider.async_call_espn_api = AsyncMock(
        return_value={
            "data": {"events": []},
            "url": "all-scoreboard",
            "timestamp": None,
        }
    )

    response = await provider._async_fetch_scoreboard_data(None, "en")
    selected = response["data"]["events"][0]

    assert selected["id"] == "selected-event"
    assert selected["season"]["slug"] == "regular-season"
    assert response["lookups"]["derived_league_name"] == "Selected Competition"

    teams = selected["competitions"][0]["competitors"]
    assert teams[0]["team"]["logo"].startswith("https://example.invalid/")
    assert teams[1]["team"]["logo"].startswith("https://example.invalid/")


@pytest.mark.asyncio
async def test_derived_league_name_picks_nearest_event_not_last_iterated():
    """/schedule is returned newest-first with no date-relevance filtering in
    the loop that builds derived_league_name, so it must not just take
    whichever event happens to be iterated last (the oldest one). Regression
    test for a real AC Milan case: their /schedule endpoint lists two recent
    Serie A results followed by four older preseason friendlies, and
    derived_league_name silently ended up as "Club Friendly" - even though
    their actual current competition is Serie A, and even though a
    same-day-relevant Serie A match is present in the list."""
    today = date.today()

    schedule_events = [
        {
            "id": "recent-serie-a",
            "date": f"{(today - timedelta(days=2)).isoformat()}T18:45Z",
            "season": {"year": 2026, "displayName": "2026-27 Italian Serie A"},
        },
        {
            "id": "older-serie-a",
            "date": f"{(today - timedelta(days=7)).isoformat()}T18:45Z",
            "season": {"year": 2026, "displayName": "2026-27 Italian Serie A"},
        },
        {
            "id": "friendly-1",
            "date": f"{(today - timedelta(days=15)).isoformat()}T14:45Z",
            "season": {"year": 2026, "displayName": "2026 Club Friendly"},
        },
        {
            "id": "friendly-2",
            "date": f"{(today - timedelta(days=40)).isoformat()}T12:00Z",
            "season": {"year": 2026, "displayName": "2026 Club Friendly"},
        },
    ]

    provider = object.__new__(EspnAllLeaguesProvider)
    provider.TEAM_SCHEDULE_KEY = "team-schedule-key"
    provider.instance_cache = {}
    provider.lookups = {"team_list": []}
    provider._coordinator = SimpleNamespace(
        name="AC Milan",
        sport_path="soccer",
        league_path="all",
        team_id="103",
        hass=None,
    )
    provider.async_call_espn_api = AsyncMock(
        side_effect=[
            {
                "data": {"team": {"nextEvent": []}},
                "url": "team-info",
                "timestamp": None,
            },
            {
                "data": {"events": schedule_events},
                "url": "team-schedule",
                "timestamp": None,
            },
        ]
    )

    result = await provider._async_get_team_schedule()

    assert result["derived_league_name"] == "Italian Serie A"


@freeze_time("2026-09-04")
@pytest.mark.asyncio
async def test_derived_league_name_ac_milan_real_capture():
    """Same bug as above, but replayed verbatim from real ESPN responses
    captured 2026-09-04 (tests/tt/captures/espn-soccer-all-{team,schedule}-
    103-ac-milan-20260904.json), not a synthetic reconstruction. AC Milan's
    real /schedule response is newest-first: two 2026-27 Serie A results
    (8/28, 8/23) followed by four older 2026 Club Friendly results
    (8/15 -> 7/25). Confirmed this fails on unpatched
    _async_get_team_schedule() (derived_league_name == "Club Friendly")."""

    team_response = {
        "data": _load_capture("espn-soccer-all-team-103-ac-milan-20260904.json"),
        "url": "team-info",
        "timestamp": None,
    }
    schedule_response = {
        "data": _load_capture("espn-soccer-all-schedule-103-ac-milan-20260904.json"),
        "url": "team-schedule",
        "timestamp": None,
    }

    provider = object.__new__(EspnAllLeaguesProvider)
    provider.TEAM_SCHEDULE_KEY = "team-schedule-key"
    provider.instance_cache = {}
    provider.lookups = {"team_list": []}
    provider._coordinator = SimpleNamespace(
        name="AC Milan",
        sport_path="soccer",
        league_path="all",
        team_id="103",
        hass=None,
    )
    provider.async_call_espn_api = AsyncMock(
        side_effect=[team_response, schedule_response]
    )

    result = await provider._async_get_team_schedule()

    assert result["derived_league_name"] == "Italian Serie A"


def _schedule_provider(events: list[dict]) -> EspnAllLeaguesProvider:
    provider = object.__new__(EspnAllLeaguesProvider)
    provider.TEAM_SCHEDULE_KEY = "team-schedule-key"
    provider.instance_cache = {}
    provider.lookups = {"team_list": []}
    provider._coordinator = SimpleNamespace(
        name="Test Team",
        sport_path="soccer",
        league_path="all",
        team_id="1",
        hass=None,
    )
    provider.async_call_espn_api = AsyncMock(
        side_effect=[
            {"data": {"team": {"nextEvent": []}}, "url": "team-info", "timestamp": None},
            {"data": {"events": events}, "url": "team-schedule", "timestamp": None},
        ]
    )
    return provider


@freeze_time("2026-09-04")
@pytest.mark.asyncio
async def test_derived_league_name_skips_unlabeled_nearer_event():
    """An event nearer to today with no usable season label must not win over
    a farther event that does have one - it should be skipped as a candidate
    entirely, not picked and produce an empty league name. Regression test
    for review feedback on PR #1 (Chreece): an unlabeled event today plus a
    valid league match yesterday must still resolve to the valid league."""
    provider = _schedule_provider(
        [
            {
                "id": "unlabeled-today",
                "date": "2026-09-04T12:00Z",
                "season": {"year": 2026},  # no displayName, no slug
            },
            {
                "id": "valid-yesterday",
                "date": "2026-09-03T12:00Z",
                "season": {"year": 2026, "displayName": "2026-27 Valid Current League"},
            },
        ]
    )

    result = await provider._async_get_team_schedule()

    assert result["derived_league_name"] == "Valid Current League"


@freeze_time("2026-09-04")
@pytest.mark.asyncio
async def test_derived_league_name_skips_unlabeled_nearer_upcoming_event():
    """Same as above but with both candidates in the future: an unlabeled
    event tomorrow must not beat a labeled event the day after."""
    provider = _schedule_provider(
        [
            {
                "id": "unlabeled-tomorrow",
                "date": "2026-09-05T12:00Z",
                "season": None,
            },
            {
                "id": "valid-in-two-days",
                "date": "2026-09-06T12:00Z",
                "season": {"year": 2026, "displayName": "2026-27 Valid Upcoming League"},
            },
        ]
    )

    result = await provider._async_get_team_schedule()

    assert result["derived_league_name"] == "Valid Upcoming League"


@freeze_time("2026-09-04")
@pytest.mark.asyncio
async def test_derived_league_name_skips_multiple_unlabeled_nearer_candidates():
    """Several unlabeled candidates closer to today than the nearest labeled
    one must all be skipped, still leaving a usable label."""
    provider = _schedule_provider(
        [
            {"id": "unlabeled-1", "date": "2026-09-04T12:00Z", "season": {}},
            {"id": "unlabeled-2", "date": "2026-09-05T12:00Z", "season": None},
            {
                "id": "unlabeled-3",
                "date": "2026-09-06T12:00Z",
                "season": {"year": 2026, "slug": "second-round"},
            },
            {
                "id": "valid-farther",
                "date": "2026-09-10T12:00Z",
                "season": {"year": 2026, "displayName": "2026-27 Valid Current League"},
            },
        ]
    )

    result = await provider._async_get_team_schedule()

    assert result["derived_league_name"] == "Valid Current League"
