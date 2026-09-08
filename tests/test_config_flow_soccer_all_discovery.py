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
async def test_custom_api_soccer_all_search_uses_discovered_teams():
    flow = TeamTrackerScoresFlowHandler()
    flow._sport_key = "XXX"
    flow._league_id = "XXX"
    flow._sport_path = "soccer"
    flow._league_path = "all"
    flow._async_get_soccer_all_teams = AsyncMock(
        return_value=[OLYMPIACOS, PAOK]
    )
    flow.async_step_select_team = AsyncMock(return_value={"type": "form"})

    with patch(
        "custom_components.teamtracker.config_flow.get_provider"
    ) as get_provider_mock:
        result = await flow.async_step_search({"search_team": "olympiacos"})

    get_provider_mock.assert_not_called()
    flow._async_get_soccer_all_teams.assert_awaited_once()
    assert flow._search_results == {
        "435": "Olympiacos (OLY - 435)",
    }
    assert flow._team_meta == {"435": OLYMPIACOS}
    assert result == {"type": "form"}
