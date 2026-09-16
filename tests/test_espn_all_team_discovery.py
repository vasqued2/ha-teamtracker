"""Regression tests for soccer/all team discovery through the provider."""

from unittest.mock import AsyncMock

import pytest

from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider


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


def _team_payload(*teams):
    return {
        "sports": [
            {
                "leagues": [
                    {
                        "teams": [{"team": team} for team in teams],
                    }
                ]
            }
        ]
    }


def test_soccer_team_payload_extracts_canonical_team():
    payload = _team_payload(OLYMPIACOS, OLYMPIACOS)

    assert EspnAllLeaguesProvider._soccer_teams_from_payload(payload) == [
        OLYMPIACOS
    ]


@pytest.mark.asyncio
async def test_soccer_all_discovery_merges_duplicate_ids():
    provider = EspnAllLeaguesProvider()
    provider.async_call_espn_api = AsyncMock(
        side_effect=[
            {
                "data": {
                    "items": [
                        {"slug": "gre.1"},
                        {"slug": "uefa.champions"},
                    ]
                },
                "url": "catalog",
                "timestamp": "now",
            },
            {
                "data": _team_payload(OLYMPIACOS, PAOK),
                "url": "gre.1",
                "timestamp": "now",
            },
            {
                "data": _team_payload({**OLYMPIACOS, "location": ""}),
                "url": "uefa.champions",
                "timestamp": "now",
            },
        ]
    )

    response = await provider._async_fetch_team_data(
        None,
        "soccer",
        "all",
        "ConfigFlow-teams",
    )

    assert [team["id"] for team in response["data"]] == ["435", "605"]
    assert provider.async_call_espn_api.await_count >= 3


@pytest.mark.asyncio
async def test_non_soccer_all_uses_original_team_fetch():
    provider = EspnAllLeaguesProvider()
    provider._coordinator = None

    # EspnProvider's normal endpoint remains authoritative outside soccer/all.
    provider.async_call_espn_api = AsyncMock(
        return_value={
            "data": _team_payload(OLYMPIACOS),
            "url": "normal",
            "timestamp": "now",
        }
    )

    response = await provider._async_fetch_team_data(
        None,
        "basketball",
        "all",
        "ConfigFlow-teams",
    )

    assert response["data"] == [OLYMPIACOS]
