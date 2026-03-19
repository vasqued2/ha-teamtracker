"""Test for config flow"""
from unittest.mock import patch
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamtracker.const import DOMAIN, CONF_API_LANGUAGE
from homeassistant import setup
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from tests.const import CONFIG_DATA


async def test_user_form(hass):
    """Test the multi-step config flow: sport → league → search → manual."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    # Step 1: init flow, expect sport selection form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: choose sport → expect league selection form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sport_key": "football"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "league"

    # Step 3: choose league → expect team search form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"league_id": "NFL"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "search"

    # Step 4: empty search → expect manual entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search_team": ""}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    # Step 5: enter team details → expect entry created
    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "team_id": "SEA",
                "conference_id": "9999",
                "name": "team_tracker",
            },
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "NFL \u2013 team_tracker"
        assert result["data"] == {
            "name": "team_tracker",
            "league_id": "NFL",
            "team_id": "SEA",
            "conference_id": "9999",
            "league_path": "nfl",
            "sport_path": "football",
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_path_form(hass):
    """Test we get the path form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "path"}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_options_flow_init(hass):
    """ Test config flow options """

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

    # Show Options Flow Form
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "form" == result["type"]
    assert "init" == result["step_id"]
    assert {} == result["errors"]

    # Submit Form with Options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"api_language": "en"}
    )

    assert "create_entry" == result["type"]
    assert "" == result["title"]
    assert {CONF_API_LANGUAGE: "en"} == result["data"]

    await hass.async_block_till_done()
