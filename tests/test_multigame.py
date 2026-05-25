"""Test NFL Sensor"""
import json
import logging

import aiofiles

from custom_components.teamtracker.const import DEFAULT_LAST_UPDATE, DEFAULT_LOGO
from custom_components.teamtracker.models import TeamTrackerValues
from custom_components.teamtracker.parse_espn import EspnParser

from tests.const import MULTIGAME_DATA

_LOGGER = logging.getLogger(__name__)


async def test_multigame(hass):
    """ Use file w/ test json and loop through test cases and compare to expected results """

    async with aiofiles.open("tests/tt/multigame.json", mode="r") as f:
        contents = await f.read()
    data = json.loads(contents)
    if data is None:
        _LOGGER.warning("test_event(): Error with test file '%s'", "tests/tt/multigame.json")
        assert False

    for t in MULTIGAME_DATA:
        sensor_name = t["sensor_name"]
        sport_path = t["sport"]
        league_path = t["league"].lower()
        league_id = t["league"]
        team_id = t["team_abbr"]
        lang = "en"
        league_map = {}

        parser = EspnParser()
        parser.setup(sensor_name, sport_path, league_path, league_id, team_id)

        url = "url"
        timestamp = "timestamp"
        provider_response = {
            "data": data,
            "url": url,
            "timestamp": timestamp
        }

        _LOGGER.debug("%s: calling async_parse_response()", sensor_name)
        values = await parser.async_parse_response(
            provider_response,
            lang,
        )

        assert values
        values_dict = values.to_dict_all_attr()

        assert values_dict["event_name"] == t["expected_event_name"]
