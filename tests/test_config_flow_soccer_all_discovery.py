"""Regression tests for Custom API soccer/all team discovery."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.teamtracker.config_flow import TeamTrackerScoresFlowHandler


OLYMPIACOS = {
    "id": "435",
    "displayName": "Olympiacos",
    "abbreviation": "OLY",
    "location": "Piraeus",
}
PAOK = {
    "id": "605",
    "displayName": "PAOK Salonika",
    "abbreviation": "PAOK",
    "location": "Thessaloniki",
}


def test_soccer_team_payload_extracts_canonical_team():
    payload = {
        "sports": [
            {
                "leagues": [
                    {
                        "teams": [
                            {"team": OLYMPIACOS},
                            {"team": OLYMPIACOS},
                        ]
                    }
                ]
            }
        ]
    }

    assert TeamTrackerScoresFlowHandler._soccer_teams_from_payload(payload) == [
        OLYMPIACOS
    ]


@pytest.mark.asyncio
async def test_soccer_all_discovery_merges_duplicate_ids():
    flow = TeamTrackerScoresFlowHandler()
    flow._async_soccer_all_league_paths = AsyncMock(
        return_value=["gre.1", "uefa.champions"]
    )
    flow._async_fetch_soccer_league_teams = AsyncMock(
        side_effect=[
            [OLYMPIACOS, PAOK],
            [{**OLYMPIACOS, "location": ""}],
        ]
    )

    teams = await flow._async_get_soccer_all_teams()

    assert [team["id"] for team in teams] == ["435", "605"]
    assert flow._async_fetch_soccer_league_teams.await_count == 2


@pytest.mark.asyncio
async def test_guided_soccer_search_uses_discovered_leagues():
    # Guided soccer search must use ESPN's discovered league collections.
    flow = TeamTrackerScoresFlowHandler()
    flow._sport_path = "soccer"

    flow._async_soccer_all_league_paths = AsyncMock(
        return_value=["gre.1", "ger.1"]
    )

    async def fake_json(url, params=None):
        if "/soccer/gre.1/teams" in url:
            return {
                "sports": [
                    {
                        "leagues": [
                            {
                                "name": "Greek Super League",
                                "teams": [
                                    {
                                        "team": {
                                            "id": "435",
                                            "displayName": "Olympiacos",
                                            "abbreviation": "OLY",
                                            "location": "Piraeus",
                                        }
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }

        if "/soccer/ger.1/teams" in url:
            return {
                "sports": [
                    {
                        "leagues": [
                            {
                                "name": "Bundesliga",
                                "teams": [
                                    {
                                        "team": {
                                            "id": "124",
                                            "displayName": "Borussia Dortmund",
                                            "abbreviation": "DOR",
                                            "location": "Dortmund",
                                        }
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }

        return None

    flow._json = AsyncMock(side_effect=fake_json)

    result = await flow._search_team_sport("olympiacos")

    flow._async_soccer_all_league_paths.assert_awaited_once()

    requested_urls = [
        call.args[0]
        for call in flow._json.await_args_list
        if call.args
    ]
    assert any("/soccer/gre.1/teams" in url for url in requested_urls)
    assert any("/soccer/ger.1/teams" in url for url in requested_urls)

    assert [(item["id"], item["displayName"]) for item in result] == [
        ("435", "Olympiacos")
    ]
    assert result[0]["competitions"] == {
        "gre.1": "Greek Super League"
    }
