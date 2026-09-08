"""Tests for TheSportsDB provider."""

from custom_components.teamtracker.parse_sportsdb import SportsDbParser
from custom_components.teamtracker.parser_factory import get_parser
from custom_components.teamtracker.provide_sportsdb import (
    SPORTSDB_DATA_FORMAT,
    SportsDbProvider,
)
from custom_components.teamtracker.provider_factory import get_provider


def test_factory():
    provider = get_provider("sportsdb", "all", "133749")
    assert isinstance(provider, SportsDbProvider)
    assert provider.data_format == SPORTSDB_DATA_FORMAT

    parser = get_parser(SPORTSDB_DATA_FORMAT, None)
    assert isinstance(parser, SportsDbParser)


def test_sport_mapping():
    expected = {
        "Soccer": "soccer",
        "Baseball": "baseball",
        "Basketball": "basketball",
        "Ice Hockey": "hockey",
        "American Football": "football",
        "Motorsport": "racing",
        "Volleyball": "volleyball",
    }

    for source, target in expected.items():
        assert SportsDbParser._normalize_sport_name(source) == target


def test_event_roots():
    provider = SportsDbProvider()

    assert provider._extract_events(
        {"events": [{"idEvent": "1"}]}
    ) == [{"idEvent": "1"}]

    assert provider._extract_events(
        {"results": [{"idEvent": "2"}]}
    ) == [{"idEvent": "2"}]


def test_status_mapping():
    provider = SportsDbProvider()

    for status in ("NS", "TBD", "PST", "POST"):
        assert provider._event_state({"strStatus": status}) == "pre"

    for status in ("1H", "Q3", "IN7", "P2", "HT"):
        assert provider._event_state({"strStatus": status}) == "in"

    for status in ("FT", "AET", "PEN", "AOT"):
        assert provider._event_state({"strStatus": status}) == "post"


def test_event_transform():
    provider = SportsDbProvider()

    team = {
        "idTeam": "133749",
        "strTeam": "PAOK",
        "strTeamShort": "PAOK",
        "strSport": "Soccer",
        "strColour1": "#000000",
        "strColour2": "#FFFFFF",
    }

    raw = {
        "idEvent": "999001",
        "strEvent": "PAOK vs Aris",
        "strEventAlternate": "ARI @ PAOK",
        "strSeason": "2026-2027",
        "idLeague": "4336",
        "strLeague": "Greek Super League",
        "strLeagueBadge": "https://example.invalid/league.png",
        "strHomeTeam": "PAOK",
        "strAwayTeam": "Aris",
        "idHomeTeam": "133749",
        "idAwayTeam": "133750",
        "intHomeScore": "3",
        "intAwayScore": "1",
        "strTimestamp": "2026-09-06T18:30:00",
        "strHomeTeamBadge": "https://example.invalid/paok.png",
        "strAwayTeamBadge": "https://example.invalid/aris.png",
        "strVenue": "Toumba Stadium",
        "strCountry": "Greece",
        "strStatus": "FT",
    }

    event = provider._build_espn_event(raw, team)

    assert event is not None
    assert event["id"] == "999001"
    assert event["date"] == "2026-09-06T18:30Z"
    assert event["status"]["type"]["state"] == "post"

    competition = event["competitions"][0]
    assert competition["altGameNote"] == "Greek Super League"
    assert competition["leagueId"] == "4336"

    home, away = competition["competitors"]

    assert home["team"]["id"] == "133749"
    assert home["team"]["abbreviation"] == "PAOK"
    assert home["score"] == "3"
    assert home["winner"] is True

    assert away["team"]["id"] == "133750"
    assert away["score"] == "1"
    assert away["winner"] is False
