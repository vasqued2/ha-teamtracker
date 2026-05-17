"""Test NFL Sensor"""
import json
import logging
import aiofiles

from custom_components.teamtracker.clear_values import async_clear_values
from custom_components.teamtracker.const import (
    DEFAULT_LAST_UPDATE,
    DEFAULT_LOGO,
)
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
        values = TeamTrackerValues()
        values.sport = t["sport"]
        values.league = t["league"]
        values.league_logo = DEFAULT_LOGO
        values.team_abbr = t["team_abbr"]
        values.state = "NOT_FOUND"
        values.last_update = DEFAULT_LAST_UPDATE
        values.private_fast_refresh = False

        sensor_name = t["sensor_name"]
        sport_path = values.sport
        league_id = values.league
        team_id = values.team_abbr
        lang = "en"
        league_map = {}

        parser = EspnParser()
        parser.setup(sensor_name, sport_path, league_id, team_id)

        _LOGGER.debug("%s: calling async_parse_response()", sensor_name)
        values = await parser.async_parse_response(
            values,
            data,
            league_map,
            lang,
        )

        assert values
        values_dict = values.to_dict_all_attr()

        assert values_dict["event_name"] == t["expected_event_name"]
