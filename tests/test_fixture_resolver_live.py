"""Regression tests for live supplemental soccer fixtures."""

from datetime import datetime, timezone

from custom_components.teamtracker.fixture_resolver_live import (
    candidate_to_live_espn_event,
    sportsdb_event_state,
)


def test_sportsdb_live_status_mapping():
    assert sportsdb_event_state({"strStatus": "NS"}) == "pre"
    assert sportsdb_event_state({"strStatus": "1H"}) == "in"
    assert sportsdb_event_state({"strStatus": "HT"}) == "in"
    assert sportsdb_event_state({"strStatus": "2H"}) == "in"
    assert sportsdb_event_state({"strStatus": "FT"}) == "post"


def test_live_candidate_preserves_score_and_status():
    candidate = {
        "source": "sportsdb",
        "id": "2593112",
        "kickoff": datetime(2026, 9, 16, 17, 0, tzinfo=timezone.utc),
        "competition": "Greek Football Cup",
        "league_id": "",
        "league_logo": "",
        "home_id": "133744",
        "home_name": "Atromitos",
        "home_logo": "https://example.invalid/atromitos.png",
        "away_id": "133749",
        "away_name": "PAOK",
        "away_logo": "https://example.invalid/paok.png",
        "tracked_home": False,
        "venue": "Peristeri Stadium",
        "state": "in",
        "status_detail": "2H",
        "home_score": "0",
        "away_score": "1",
    }

    event = candidate_to_live_espn_event(
        candidate,
        espn_team_id="605",
        team_name="PAOK",
        team_logo="https://example.invalid/espn-paok.png",
    )

    assert event["status"]["type"]["state"] == "in"
    assert event["status"]["type"]["shortDetail"] == "2H"

    competition = event["competitions"][0]
    assert competition["status"]["type"]["state"] == "in"

    home, away = competition["competitors"]
    assert home["score"] == "0"
    assert away["score"] == "1"
    assert away["team"]["id"] == "605"
    assert away["team"]["displayName"] == "PAOK"


def test_post_candidate_sets_winner():
    candidate = {
        "source": "sportsdb",
        "id": "event-1",
        "kickoff": datetime(2026, 9, 16, 17, 0, tzinfo=timezone.utc),
        "competition": "Cup",
        "home_id": "home",
        "home_name": "Home",
        "away_id": "away",
        "away_name": "Tracked",
        "tracked_home": False,
        "state": "post",
        "status_detail": "FT",
        "home_score": "0",
        "away_score": "2",
    }

    event = candidate_to_live_espn_event(
        candidate,
        espn_team_id="99",
        team_name="Tracked",
    )

    home, away = event["competitions"][0]["competitors"]
    assert event["status"]["type"]["completed"] is True
    assert home["winner"] is False
    assert away["winner"] is True
