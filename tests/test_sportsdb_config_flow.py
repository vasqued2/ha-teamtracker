"""Config-flow tests for the standalone TheSportsDB provider."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import setup

from custom_components.teamtracker.const import (
    CONF_SPORTSDB_API_KEY,
    DOMAIN,
)


TEAM_RAW = {
    "idTeam": "133749",
    "strTeam": "PAOK",
    "strTeamShort": "PAOK",
    "strSport": "Soccer",
    "idLeague": "4336",
    "strLeague": "Greek Super League",
}


async def _start_sportsdb_flow(hass):
    await setup.async_setup_component(
        hass,
        "persistent_notification",
        {},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"sport_key": "SPORTSDB"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "sportsdb"

    return result


async def test_sportsdb_free_team_id_flow(hass):
    """Free key: configure a standalone sensor using numeric team ID."""

    lookup = AsyncMock(
        return_value={
            "data": {"teams": [TEAM_RAW]},
            "url": (
                "https://www.thesportsdb.com/"
                "api/v1/json/***/lookupteam.php?id=133749"
            ),
            "timestamp": "2026-09-07T18:00:00+00:00",
        }
    )

    with patch(
        "custom_components.teamtracker.provide_sportsdb."
        "SportsDbProvider.async_lookup_team",
        lookup,
    ):
        result = await _start_sportsdb_flow(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "sportsdb_api_key": "",
                "search_team": "",
                "team_id": "133749",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "sportsdb_select_team"

    lookup.assert_awaited_once()
    assert lookup.await_args.kwargs["api_key"] == "123"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"team_selection": "133749"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "finalize"

    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "SPORTSDB - PAOK"

    assert result["data"] == {
        "name": "SPORTSDB - PAOK",
        "league_id": "SPORTSDB",
        "team_id": "133749",
        "sport_path": "sportsdb",
        "league_path": "4336",
    }


async def test_sportsdb_supporter_name_search_flow(hass):
    """Supporter key: search by name and persist provider credentials."""

    search = AsyncMock(
        return_value={
            "data": [
                {
                    "id": "133749",
                    "abbreviation": "PAOK",
                    "displayName": "PAOK",
                    "location": "Thessaloniki",
                    "sport": "Soccer",
                    "league_id": "4336",
                    "league_name": "Greek Super League",
                }
            ],
            "url": (
                "https://www.thesportsdb.com/"
                "api/v1/json/***/searchteams.php?t=PAOK"
            ),
            "timestamp": "2026-09-07T18:00:00+00:00",
        }
    )

    with patch(
        "custom_components.teamtracker.provide_sportsdb."
        "SportsDbProvider.async_search_teams",
        search,
    ):
        result = await _start_sportsdb_flow(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "sportsdb_api_key": "supporter-secret",
                "search_team": "PAOK",
                "team_id": "",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "sportsdb_select_team"

    search.assert_awaited_once()
    assert search.await_args.kwargs["api_key"] == "supporter-secret"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"team_selection": "133749"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "finalize"

    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "SPORTSDB - PAOK"

    assert result["data"]["league_id"] == "SPORTSDB"
    assert result["data"]["team_id"] == "133749"
    assert result["data"]["sport_path"] == "sportsdb"
    assert result["data"]["league_path"] == "4336"
    assert (
        result["data"]["sportsdb_api_key"]
        == "supporter-secret"
    )

    # Credential must not leak into title/name.
    assert "supporter-secret" not in result["title"]
    assert "supporter-secret" not in result["data"]["name"]



async def test_sportsdb_options_keep_change_clear(hass):
    """SportsDB options must keep, replace, and explicitly clear secrets."""

    base_data = {
        "name": "SPORTSDB - PAOK",
        "league_id": "SPORTSDB",
        "team_id": "133749",
        "sport_path": "sportsdb",
        "league_path": "4336",
        "sportsdb_api_key": "original-supporter-key",
    }

    # Blank password + clear=False must preserve the existing credential.
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SPORTSDB - PAOK",
        data=base_data,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "api_language": "",
            "sportsdb_api_key": "",
            "sportsdb_clear_api_key": False,
        },
    )

    assert result["type"] == "create_entry"
    assert CONF_SPORTSDB_API_KEY not in result["data"]

    # Entering a new key must replace the effective credential via options.
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="SPORTSDB - PAOK 2",
        data=base_data,
    )
    entry2.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry2.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "api_language": "",
            "sportsdb_api_key": "replacement-supporter-key",
            "sportsdb_clear_api_key": False,
        },
    )

    assert result["type"] == "create_entry"
    assert (
        result["data"][CONF_SPORTSDB_API_KEY]
        == "replacement-supporter-key"
    )

    # Explicit clear must write an empty override. The provider interprets
    # that as the public free key rather than exposing/removing entry.data.
    entry3 = MockConfigEntry(
        domain=DOMAIN,
        title="SPORTSDB - PAOK 3",
        data=base_data,
    )
    entry3.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry3.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "api_language": "",
            "sportsdb_api_key": "",
            "sportsdb_clear_api_key": True,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_SPORTSDB_API_KEY] == ""



async def test_sportsdb_options_false_string_preserves_key(hass):
    """A false-like checkbox value must never clear an existing key."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SPORTSDB - PAOK",
        data={
            "name": "SPORTSDB - PAOK",
            "league_id": "SPORTSDB",
            "team_id": "133749",
            "sport_path": "sportsdb",
            "league_path": "4336",
        },
        options={
            "api_language": "",
            "sportsdb_api_key": "replacement-supporter-key",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id
    )

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "api_language": "",
            "sportsdb_api_key": "",
            "sportsdb_clear_api_key": "false",
        },
    )

    assert result["type"] == "create_entry"
    assert (
        result["data"]["sportsdb_api_key"]
        == "replacement-supporter-key"
    )


async def test_sportsdb_options_true_string_clears_key(hass):
    """A true-like checkbox value must explicitly select the free key."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SPORTSDB - PAOK",
        data={
            "name": "SPORTSDB - PAOK",
            "league_id": "SPORTSDB",
            "team_id": "133749",
            "sport_path": "sportsdb",
            "league_path": "4336",
        },
        options={
            "api_language": "",
            "sportsdb_api_key": "replacement-supporter-key",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "api_language": "",
            "sportsdb_api_key": "",
            "sportsdb_clear_api_key": "true",
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"]["sportsdb_api_key"] == ""
