"""Test NFL Sensor"""
import asyncio
import aiohttp
import aiofiles

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamtracker.const import DOMAIN
from tests.const import CONFIG_DATA


async def test_sensor(hass, mocker):

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NFL",
        data=CONFIG_DATA,
    )

    mocker.patch("locale.getlocale", return_value=("en", 0))

    contents = "{}"
    mocker.patch('aiofiles.open', return_value=mocker.mock_open(read_data=contents).return_value)

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "teamtracker" in hass.config.components
