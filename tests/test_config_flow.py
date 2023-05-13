"""Test for config flow"""
from unittest.mock import patch

import pytest

from custom_components.teamtracker.const import DOMAIN
from homeassistant import setup


@pytest.mark.parametrize(
    "input,step_id,title,description,data",
    [
        (
            {
                "league_id": "NFL",
                "team_id": "SEA",
                "name": "team_tracker",
                "timeout": 120,
                "conference_id": "9999",
            },
            "user",
            "team_tracker",
            "description",
            {
                "league_id": "NFL",
                "team_id": "SEA",
                "name": "team_tracker",
                "timeout": 120,
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
