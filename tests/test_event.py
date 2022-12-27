"""Test NFL Sensor"""
from pytest_homeassistant_custom_component.common import MockConfigEntry
import asyncio
import aiohttp
import aiofiles
import json
import logging

_LOGGER = logging.getLogger(__name__)

from custom_components.teamtracker.const import DOMAIN, DEFAULT_LOGO, DEFAULT_LAST_UPDATE
from tests.const import CONFIG_DATA, TEST_DATA
from custom_components.teamtracker.clear_values import async_clear_values
from custom_components.teamtracker.event import async_process_event


async def test_eventzxc(hass):

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NFL",
        data=CONFIG_DATA[0],
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "teamtracker" in hass.config.components

#
#  New test 
#

    async with aiofiles.open('tests/tt/all.json', mode='r') as f:
        contents = await f.read()
    data = json.loads(contents)
    if data is None:
        values["api_message"] = "Test file error, no data returned"
        _LOGGER.warn("test_event(): Error with test file '%s'", "tests/tt/all.json")
        assert False

    for t in TEST_DATA:
        values = await async_clear_values()
        values["sport"] = t["sport"]
        values["league"] = t["league"]
        values["league_logo"] = DEFAULT_LOGO
        values["team_abbr"] = t["team_abbr"]
        values["state"] = "NOT_FOUND"
        values["last_update"] = DEFAULT_LAST_UPDATE
        values["private_fast_refresh"] = False

        sensor_name = t["sensor_name"]
        sport_path = values["sport"]
        league_id = values["league"]
        team_id = values["team_abbr"]
        lang = "en"
        url = "tests/tt/all.json"

        _LOGGER.debug("%s: calling async_process_event()", sensor_name)
        values = await async_process_event(values, sensor_name, data, sport_path, league_id, DEFAULT_LOGO, team_id, lang, url)

        assert values

        file = "tests/tt/results/" + sensor_name + ".json"
        async with aiofiles.open(file, mode='r') as f:
            contents = await f.read()
        expected_results = json.loads(contents)

        assert values == expected_results