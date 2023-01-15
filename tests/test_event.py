"""Test NFL Sensor"""
import json
import logging

import aiofiles

_LOGGER = logging.getLogger(__name__)

from custom_components.teamtracker.clear_values import async_clear_values
from custom_components.teamtracker.const import (
    DEFAULT_KICKOFF_IN,
    DEFAULT_LAST_UPDATE,
    DEFAULT_LOGO,
)
from custom_components.teamtracker.event import async_process_event

from tests.const import TEST_DATA


async def test_event(hass):

    async with aiofiles.open("tests/tt/all.json", mode="r") as f:
        contents = await f.read()
    data = json.loads(contents)
    if data is None:
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

        _LOGGER.debug("%s: calling async_process_event()", sensor_name)
        values = await async_process_event(
            values,
            sensor_name,
            data,
            sport_path,
            league_id,
            DEFAULT_LOGO,
            team_id,
            lang,
        )

        assert values

        file = "tests/tt/results/" + sensor_name + ".json"
        async with aiofiles.open(file, mode="r") as f:
            contents = await f.read()
        expected_results = json.loads(contents)

        values["kickoff_in"] = DEFAULT_KICKOFF_IN  # set to default value for compare
        assert values == expected_results
