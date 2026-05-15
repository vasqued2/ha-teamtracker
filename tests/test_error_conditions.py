"""Test NFL Sensor"""
import logging

from custom_components.teamtracker.parse_espn import EspnParser

_LOGGER = logging.getLogger(__name__)


async def test_error_conditions(hass):
    """ Use file w/ test json and loop through test cases and compare to expected results """

    parser = EspnParser()
    parser.setup("sensor_name", "sport_path", "league_id", "team_id")

    rc = await parser._async_set_cricket_values({}, 0, 0)
    assert rc is False
    rc = await parser._async_set_golf_values({}, 0, 0)
    assert rc is False
    rc = await parser._async_set_hockey_values({}, 0, 0)
    assert rc is False
    rc = await parser._async_set_mma_values({}, 0, 0)
    assert rc is False
    rc = await parser._async_set_racing_values({}, 0, 0)
    assert rc is False
    rc = await parser._async_set_soccer_values({}, 0, 0)
    assert rc is False
    rc = await parser._async_set_tennis_values({}, 0, 0, 0)
    assert rc is False
    rc = await parser._async_set_volleyball_values({}, 0, 0)
    assert rc is False

    rc = await parser._async_set_values({}, {}, 0, 0, 0)
    assert rc is False
    rc = await parser._async_set_universal_values({}, 0, 0, 0)
    assert rc is False
    rc = await parser._async_set_team_values({}, 0, 0, 0)
    assert rc is False
    rc = await parser._async_set_in_values({}, 0, 0, 0)
    assert rc is False
