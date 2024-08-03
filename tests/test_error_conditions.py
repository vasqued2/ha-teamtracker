"""Test NFL Sensor"""
import logging

from custom_components.teamtracker.set_cricket import async_set_cricket_values
from custom_components.teamtracker.set_golf import async_set_golf_values
from custom_components.teamtracker.set_hockey import async_set_hockey_values
from custom_components.teamtracker.set_mma import async_set_mma_values
from custom_components.teamtracker.set_racing import async_set_racing_values
from custom_components.teamtracker.set_soccer import async_set_soccer_values
from custom_components.teamtracker.set_tennis import async_set_tennis_values
from custom_components.teamtracker.set_volleyball import async_set_volleyball_values
from custom_components.teamtracker.set_values import async_set_values, async_set_universal_values, async_set_team_values, async_set_in_values

_LOGGER = logging.getLogger(__name__)


async def test_error_conditions(hass):
    """ Use file w/ test json and loop through test cases and compare to expected results """

    rc = await async_set_cricket_values({}, {}, 0, 0, "en", "sensor_name")
    assert rc is False
    rc = await async_set_golf_values({}, {}, 0, 0, "en", "sensor_name")
    assert rc is False
    rc = await async_set_hockey_values({}, {}, 0, 0, "sensor_name")
    assert rc is False
    rc = await async_set_mma_values({}, {}, 0, 0, "en", "sensor_name")
    assert rc is False
    rc = await async_set_racing_values({}, {}, 0, 0, "en", "sensor_name")
    assert rc is False
    rc = await async_set_soccer_values({}, {}, 0, 0, "sensor_name")
    assert rc is False
    rc = await async_set_tennis_values({}, {}, 0, 0, 0, "en", "sensor_name")
    assert rc is False
    rc = await async_set_volleyball_values({}, {}, 0, 0, "sensor_name")
    assert rc is False

    rc = await async_set_values({}, {}, 0, 0, 0, "en", "sensor_name")
    assert rc is False
    rc = await async_set_universal_values({}, {}, 0, 0, 0, "en", "sensor_name")
    assert rc is False
    rc = await async_set_team_values({}, {}, 0, 0, 0, "en", "sensor_name")
    assert rc is False
    rc = await async_set_in_values({}, {}, 0, 0, 0, "sensor_name")
    assert rc is False
