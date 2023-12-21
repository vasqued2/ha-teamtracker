"""Test for config flow"""
from unittest.mock import patch
from pytest_homeassistant_custom_component.common import MockConfigEntry

import pytest

from custom_components.teamtracker.const import DOMAIN, CONF_API_LANGUAGE
from homeassistant import setup


@pytest.mark.parametrize(
    "input,step_id,title,description,data",
    [
        (
            {
                "league_id": "NFL",
                "team_id": "SEA",
                "name": "team_tracker",
                "conference_id": "9999",
            },
            "user",
            "team_tracker",
            "description",
            {
                "league_id": "NFL",
                "team_id": "SEA",
                "name": "team_tracker",
                "conference_id": "9999",
                "league_path": "nfl",
                "sport_path": "football",
            },
        ),
    ],
)
async def test_user_form(
    input,  # pylint: disable=redefined-builtin
    step_id,
    title,
    description,
    data,
    hass,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": step_id}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input
        )

        assert result2["type"] == "create_entry"
        assert result2["title"] == title
        assert result2["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_path_form(
    hass,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "path"}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

#@patch("custom_components.teamtracker.sensor.async_add_entities")
async def test_options_flow_init(hass):
    """Test config flow options."""
#    m_instance = AsyncMock()
#    m_instance.getitem = AsyncMock()
#    m_github.return_value = m_instance

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="teamtracker_mock_config",
        data={
            "league_id": "MLB",
            "team_id": "MIA",
            "name": "test_tt_all_test01",
            "timeout": 120,
            "conference_id": "9999",
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # show initial form
#    result = await hass.config_entries.options.async_init(config_entry.entry_id)

#    assert "form" == result["type"]
#    assert "init" == result["step_id"]
#    assert {} == result["errors"]
