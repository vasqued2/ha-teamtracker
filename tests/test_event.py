"""Test NFL Sensor"""
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamtracker.const import DOMAIN
from tests.const import CONFIG_DATA


async def test_sensor(hass):

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NFL",
        data=CONFIG_DATA[0],
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "teamtracker" in hass.config.components

    state = hass.states.get("sensor.test_tt_all_test01")

    assert state
    assert state.state == "PRE"