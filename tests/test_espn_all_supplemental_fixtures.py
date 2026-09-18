"""Regression tests for supplemental fixtures on ESPN soccer/all sensors."""

from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider
from custom_components.teamtracker.provide_espn_all_supplemented import (
    SupplementalEspnAllLeaguesProvider,
)
from custom_components.teamtracker.provider_factory import get_provider


def _event(
    event_id: str,
    kickoff: str,
    *,
    team_id: str,
    team_name: str,
    opponent_id: str,
    opponent_name: str,
    tracked_home: bool,
    source: str | None = None,
) -> dict:
    tracked = {
        "id": team_id,
        "type": "team",
        "homeAway": "home" if tracked_home else "away",
        "team": {
            "id": team_id,
            "displayName": team_name,
            "abbreviation": team_name,
        },
    }
    opponent = {
        "id": opponent_id,
        "type": "team",
        "homeAway": "away" if tracked_home else "home",
        "team": {
            "id": opponent_id,
            "displayName": opponent_name,
            "abbreviation": opponent_name,
        },
    }
    competitors = [tracked, opponent] if tracked_home else [opponent, tracked]
    event = {
        "id": event_id,
        "date": kickoff,
        "status": {
            "type": {
                "state": "pre",
                "completed": False,
                "shortDetail": "Scheduled",
            }
        },
        "competitions": [
            {
                "id": event_id,
                "date": kickoff,
                "competitors": competitors,
            }
        ],
    }
    if source:
        event["_teamtracker_fixture_source"] = source
    return event


def test_factory_routes_only_soccer_all_to_supplemented_provider():
    soccer = get_provider("soccer", "all", "605")
    basketball = get_provider("basketball", "all", "1")

    assert isinstance(soccer, SupplementalEspnAllLeaguesProvider)
    assert isinstance(basketball, EspnAllLeaguesProvider)
    assert not isinstance(basketball, SupplementalEspnAllLeaguesProvider)


def test_duplicate_supplemental_fixture_keeps_espn_event():
    espn = _event(
        "espn-league",
        "2026-09-19T16:30:00Z",
        team_id="124",
        team_name="Borussia Dortmund",
        opponent_id="134",
        opponent_name="VfB Stuttgart",
        tracked_home=True,
    )
    supplemental = _event(
        "sportsdb:2508365",
        "2026-09-19T16:35:00Z",
        team_id="124",
        team_name="Borussia Dortmund",
        opponent_id="sportsdb:134",
        opponent_name="Stuttgart",
        tracked_home=True,
        source="sportsdb",
    )

    merged, added = SupplementalEspnAllLeaguesProvider._merge_supplemental_events(
        {"data": {"events": [espn]}},
        [supplemental],
        "124",
    )

    assert [event["id"] for event in merged["data"]["events"]] == ["espn-league"]
    assert added == []


def test_missing_cup_fixture_is_added_before_later_espn_league_fixture():
    league = _event(
        "espn-league",
        "2026-09-20T18:00:00Z",
        team_id="605",
        team_name="PAOK",
        opponent_id="11431",
        opponent_name="Panetolikos",
        tracked_home=False,
    )
    cup = _event(
        "sportsdb:2593112",
        "2026-09-16T17:00:00Z",
        team_id="605",
        team_name="PAOK",
        opponent_id="sportsdb:10",
        opponent_name="Atromitos",
        tracked_home=False,
        source="sportsdb",
    )

    merged, added = SupplementalEspnAllLeaguesProvider._merge_supplemental_events(
        {"data": {"events": [league]}},
        [cup],
        "605",
    )

    assert [event["id"] for event in merged["data"]["events"]] == [
        "sportsdb:2593112",
        "espn-league",
    ]
    assert [event["id"] for event in added] == ["sportsdb:2593112"]
