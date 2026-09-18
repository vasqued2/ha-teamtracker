"""Regression tests for ESPN ALL fallback event normalization."""

from datetime import date, timedelta

from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider


def _fallback_event(event_date: date) -> dict:
    return {
        "id": "fallback-event",
        "date": f"{event_date.isoformat()}T18:00Z",
        "season": {
            "year": 2026,
            "displayName": "2026-27 Test Competition",
        },
        "seasonType": {"name": "Regular Season"},
        "competitions": [
            {
                "id": "fallback-event",
                "date": f"{event_date.isoformat()}T18:00Z",
                "competitors": [
                    {
                        "id": "100",
                        "type": "team",
                        "score": {
                            "value": 1,
                            "displayValue": "1",
                        },
                        "team": {
                            "id": "100",
                            "displayName": "Team A",
                            "logos": [
                                {
                                    "href": "https://example.invalid/team-a.png",
                                }
                            ],
                        },
                    },
                    {
                        "id": "200",
                        "type": "team",
                        "score": {
                            "value": 3,
                            "displayValue": "3",
                        },
                        "team": {
                            "id": "200",
                            "displayName": "Team B",
                        },
                    },
                ],
            }
        ],
    }


def _scores(event: dict) -> list:
    return [
        competitor["score"]
        for competitor in event["competitions"][0]["competitors"]
    ]


def test_next_event_fallback_returns_scalar_scores():
    today = date.today()
    event = _fallback_event(today + timedelta(days=1))

    result = EspnAllLeaguesProvider._next_event_response_for_dates(
        {
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

    selected = result["data"]["events"][0]

    assert _scores(selected) == ["1", "3"]

    # Fallback normalization must not mutate ESPN's cached source payload.
    assert isinstance(_scores(event)[0], dict)
    assert isinstance(_scores(event)[1], dict)


def test_schedule_fallback_returns_scalar_scores():
    today = date.today()
    event = _fallback_event(today + timedelta(days=1))

    cached = {
        "data": {"events": [event]},
        "url": "team-schedule",
        "timestamp": None,
    }

    result = EspnAllLeaguesProvider._schedule_response_for_dates(
        {"schedule_response": cached},
        (
            f"{today.strftime('%Y%m%d')}-"
            f"{(today + timedelta(days=1)).strftime('%Y%m%d')}"
        ),
    )

    selected = result["data"]["events"][0]

    assert _scores(selected) == ["1", "3"]

    # Cached schedule data must remain untouched.
    assert isinstance(_scores(event)[0], dict)
    assert isinstance(_scores(event)[1], dict)
