"""Test NFL Sensor"""
import logging

from custom_components.teamtracker.parse_espn import EspnParser

_LOGGER = logging.getLogger(__name__)


async def test_error_conditions(hass):
    """ Use file w/ test json and loop through test cases and compare to expected results """

    parser = EspnParser(None)
    parser.setup("sensor_name", "sport_path", "league_path", "league_id", "team_id")

    rc = parser._set_cricket_values({}, 0, 0)
    assert rc is False
    rc = parser._set_golf_values({}, 0, 0)
    assert rc is False
    rc = parser._set_hockey_values({}, 0, 0)
    assert rc is False
    rc = parser._set_mma_values({}, 0, 0)
    assert rc is False
    rc = parser._set_racing_values({}, 0, 0)
    assert rc is False
    rc = parser._set_soccer_values({}, 0, 0)
    assert rc is False
    rc = parser._set_tennis_values({}, 0, 0, 0)
    assert rc is False
    rc = parser._set_volleyball_values({}, 0, 0)
    assert rc is False

    rc = parser._set_values({}, 0, 0, 0)
    assert rc is False
    rc = parser._set_universal_values({}, 0, 0, 0)
    assert rc is False
    rc = parser._set_team_values({}, 0, 0, 0)
    assert rc is False
    rc = parser._set_in_values({}, 0, 0, 0)
    assert rc is False
