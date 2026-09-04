"""Tests for the guided Team Tracker config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamtracker.config_flow import (
    ALL_COMPETITIONS,
    TeamTrackerScoresFlowHandler,
)
from custom_components.teamtracker.const import CONF_API_LANGUAGE, DOMAIN
from homeassistant import setup
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from tests.const import CONFIG_DATA


async def test_guided_team_all_entry(hass):
    """Sport -> team -> All stores a stable canonical ESPN ID."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    team = {
        "id": "435",
        "kind": "team",
        "displayName": "Olympiacos",
        "abbreviation": "OLY",
        "location": "Piraeus",
        "competitions": {
            "gre.1": "Greek Super League",
            "uefa.champions": "UEFA Champions League",
        },
    }

    with (
        patch.object(
            TeamTrackerScoresFlowHandler,
            "_search_team_sport",
            new=AsyncMock(return_value=[team]),
        ),
        patch.object(
            TeamTrackerScoresFlowHandler,
            "_verified_team_competitions",
            new=AsyncMock(return_value=team["competitions"]),
        ),
        patch.object(
            TeamTrackerScoresFlowHandler,
            "_localized_all_competitions",
            new=AsyncMock(return_value="All competitions"),
        ),
        patch(
            "custom_components.teamtracker.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"sport": "soccer"}
        )
        assert result["step_id"] == "search"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"search_competitor": "olympiakos"}
        )
        assert result["step_id"] == "select_competitor"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"competitor": "team:435"}
        )
        assert result["step_id"] == "competition"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"competition": ALL_COMPETITIONS}
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "Olympiacos"
        assert result["data"] == {
            "name": "Olympiacos",
            "league_id": "XXX",
            "team_id": "435",
            "sport_path": "soccer",
            "league_path": "all",
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_guided_athlete_specific_entry(hass):
    """Athlete discovery can create a specific verified competition entry."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    athlete = {
        "id": "2869",
        "kind": "athlete",
        "displayName": "Stefanos Tsitsipas",
        "location": "Greece",
        "competitions": {},
    }

    with (
        patch.object(
            TeamTrackerScoresFlowHandler,
            "_search_individual_sport",
            new=AsyncMock(return_value=[athlete]),
        ),
        patch.object(
            TeamTrackerScoresFlowHandler,
            "_verified_athlete_competitions",
            new=AsyncMock(return_value={"atp": "ATP"}),
        ),
        patch.object(
            TeamTrackerScoresFlowHandler,
            "_localized_all_competitions",
            new=AsyncMock(return_value="All competitions"),
        ),
        patch(
            "custom_components.teamtracker.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"sport": "tennis"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"search_competitor": "tsitsipas"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"competitor": "athlete:2869"}
        )
        assert result["step_id"] == "competition"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"competition": "atp"}
        )
        assert result["type"] == "create_entry"
        assert result["data"] == {
            "name": "Stefanos Tsitsipas",
            "league_id": "ATP",
            "team_id": "Stefanos Tsitsipas",
            "sport_path": "tennis",
            "league_path": "atp",
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_search_error_stays_in_selected_sport(hass):
    """No result is reported without falling through to another sport."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch.object(
        TeamTrackerScoresFlowHandler,
        "_search_team_sport",
        new=AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"sport": "soccer"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"search_competitor": "does-not-exist"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "search"
        assert result["errors"] == {
            "search_competitor": "no_competitors_found"
        }


async def test_custom_api_all_entry(hass):
    """Advanced mode can still create universal entries without discovery."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"sport": "custom_api"}
        )
        assert result["step_id"] == "custom_api"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "sport_path": "tennis",
                "league_path": "all",
                "team_id": "2869",
                "conference_id": "",
                "name": "Tsitsipas",
            },
        )
        assert result["type"] == "create_entry"
        assert result["data"] == {
            "name": "Tsitsipas",
            "league_id": "XXX",
            "team_id": "2869",
            "sport_path": "tennis",
            "league_path": "all",
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


def test_fuzzy_transliteration_and_id_only_dedup_helpers() -> None:
    """Olympiakos matches Olympiacos without conflating different team IDs."""
    flow = TeamTrackerScoresFlowHandler()
    assert flow._matches_search("olympiakos", "Olympiacos")
    assert flow._matches_search("TSITSIPAS", "Stefanos Tsitsipas")

    labels = flow._result_labels(
        [
            {
                "id": "435",
                "kind": "team",
                "displayName": "Olympiacos",
                "competitions": {"gre.1": "Greek Super League"},
            },
            {
                "id": "131834",
                "kind": "team",
                "displayName": "Olympiacos",
                "competitions": {"uefa.womens": "Women's Competition"},
            },
        ]
    )
    assert len(labels) == 2
    assert "435" not in labels[0][1]
    assert "131834" not in labels[1][1]
    assert "Greek Super League" in labels[0][1]
    assert "Women\'s Competition" in labels[1][1]


def test_athlete_extraction_uses_only_top_level_objects() -> None:
    """Nested article/event names can never become athlete search results."""
    pages = [
        {
            "items": [
                {
                    "id": "2869",
                    "displayName": "Stefanos Tsitsipas",
                    "birthPlace": {"summary": "Athens, Greece"},
                    "links": [
                        {
                            "id": "99999999",
                            "displayName": "Tsitsipas wins a match",
                        }
                    ],
                }
            ]
        }
    ]
    athletes = TeamTrackerScoresFlowHandler._athletes_from_pages(pages)
    assert athletes == [
        {
            "id": "2869",
            "kind": "athlete",
            "displayName": "Stefanos Tsitsipas",
            "location": "Athens, Greece",
            "competitions": {},
        }
    ]


async def test_options_flow_init(hass, mock_call_espn_api):
    """Existing API language options continue to work."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["errors"] == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"api_language": "en"}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == ""
    assert result["data"] == {CONF_API_LANGUAGE: "en"}


async def test_individual_search_uses_sport_checked_canonical_search_ids(monkeypatch):
    """Generic ESPN search is fast but cross-sport leakage is rejected locally."""
    flow = TeamTrackerScoresFlowHandler()
    flow._sport_path = "golf"
    payload = {
        "results": [
            {
                "type": "player",
                "contents": [
                    {
                        "id": "opaque-content-id",
                        "uid": "s:1100~a:3470",
                        "type": "player",
                        "sport": "golf",
                        "displayName": "Rory McIlroy",
                        "description": "Golf",
                        "link": {
                            "web": "https://www.espn.com/golf/player/_/id/3470/rory-mcilroy"
                        },
                    },
                    {
                        "id": "another-opaque-id",
                        "uid": "s:600~a:22081",
                        "type": "player",
                        "sport": "soccer",
                        "displayName": "Mark McIlroy",
                        "description": "Soccer",
                        "link": {
                            "web": "https://www.espn.com/soccer/player/_/id/22081/mark-mcilroy"
                        },
                    },
                ],
            }
        ]
    }

    async def fake_json(_url, _params=None):
        return payload

    monkeypatch.setattr(flow, "_json", fake_json)
    results = await flow._search_individual_sport("mcilroy")
    assert [item["id"] for item in results] == ["3470"]
    assert results[0]["displayName"] == "Rory McIlroy"


async def test_tsitsipas_search_accepts_lowercase_and_canonical_uid(monkeypatch):
    """Lowercase search returns canonical Tsitsipas ID instead of the search UUID."""
    flow = TeamTrackerScoresFlowHandler()
    flow._sport_path = "tennis"
    payload = {
        "results": [
            {
                "type": "player",
                "contents": [
                    {
                        "id": "eeae43af-cdf0-43b4-7dd4-2475555a445e",
                        "uid": "s:850~l:851~a:2869",
                        "type": "player",
                        "sport": "tennis",
                        "displayName": "Stefanos Tsitsipas",
                        "description": "Tennis",
                        "link": {
                            "web": "https://www.espn.com/tennis/player/_/id/2869/stefanos-tsitsipas"
                        },
                    }
                ],
            }
        ]
    }

    async def fake_json(_url, _params=None):
        return payload

    monkeypatch.setattr(flow, "_json", fake_json)
    results = await flow._search_individual_sport("tsitsipas")
    assert [(item["id"], item["displayName"]) for item in results] == [
        ("2869", "Stefanos Tsitsipas")
    ]
