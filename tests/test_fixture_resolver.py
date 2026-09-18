"""Regression tests for the supplemental soccer fixture resolver."""

from datetime import datetime, timezone

from custom_components.teamtracker.fixture_resolver import (
    candidate_to_espn_event,
    dedupe_candidates,
    name_score,
)


def _candidate(source: str, event_id: str, kickoff: str) -> dict:
    return {
        "source": source,
        "id": event_id,
        "kickoff": datetime.fromisoformat(kickoff.replace("Z", "+00:00")).astimezone(timezone.utc),
        "competition": "Greek Cup",
        "league_id": "cup",
        "league_logo": "",
        "home_id": "10",
        "home_name": "Atromitos",
        "home_logo": "",
        "away_id": "20",
        "away_name": "PAOK",
        "away_logo": "",
        "tracked_home": False,
        "venue": "Peristeri Stadium",
    }


def test_name_matching_handles_provider_variants():
    assert name_score("PAOK Salonika", "PAOK") >= 0.9
    assert name_score("Borussia Dortmund", "Dortmund") >= 0.9
    assert name_score("PAOK", "Panathinaikos") < 0.72


def test_cross_provider_candidates_are_deduplicated_by_fixture_identity():
    sportsdb = _candidate("sportsdb", "2593112", "2026-09-16T17:00:00Z")
    openfoot = _candidate("openfoot", "match-1", "2026-09-16T17:05:00Z")

    unique = dedupe_candidates([openfoot, sportsdb])

    assert len(unique) == 1
    assert unique[0]["source"] == "sportsdb"


def test_candidate_conversion_preserves_espn_tracked_team_identity():
    candidate = _candidate("sportsdb", "2593112", "2026-09-16T17:00:00Z")

    event = candidate_to_espn_event(
        candidate,
        espn_team_id="605",
        team_name="PAOK",
        team_logo="https://example.invalid/paok.png",
    )

    competition = event["competitions"][0]
    home, away = competition["competitors"]

    assert event["id"] == "sportsdb:2593112"
    assert event["status"]["type"]["state"] == "pre"
    assert competition["altGameNote"] == "Greek Cup"
    assert away["team"]["id"] == "605"
    assert away["team"]["displayName"] == "PAOK"
    assert away["team"]["logo"] == "https://example.invalid/paok.png"
    assert home["team"]["id"].startswith("sportsdb:")
