""" Test TeamTracker Sensor """
from freezegun import freeze_time

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from typing import Any
from custom_components.teamtracker.const import DOMAIN
from custom_components.teamtracker.sensor import async_setup_platform
from tests.const import CONFIG_DATA, PLATFORM_TEST_DATA
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN


@pytest.fixture(autouse=False)
def expected_lingering_timers() -> bool:
    """"  Temporary ability to bypass test failures due to lingering timers.
        Parametrize to True to bypass the pytest failure.
        @pytest.mark.parametrize("expected_lingering_timers", [True])
        This should be removed when all lingering timers have been cleaned up.
    """
    return False


#@pytest.mark.parametrize("expected_lingering_timers", [True])
@freeze_time("2026-03-21 10:00:00")
async def test_sensor(hass, mock_call_espn_api, mocker):
    """ test sensor """

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NFL",
        data=CONFIG_DATA,
    )

    mocker.patch("locale.getlocale", return_value=("en", 0))

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "teamtracker" in hass.config.components

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

#
# Validate sensor state and attributes based on CONFIG_DATA3
#

    sensor_state = hass.states.get("sensor.test_tt_all_test01")

    assert sensor_state.state == "PRE"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "MIA"
    sport = sensor_state.attributes.get("sport")
    assert sport == "baseball"
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == "Major League Baseball"
    event_name = sensor_state.attributes.get("event_name")
    assert event_name == "MIA @ PHI"
    date = sensor_state.attributes.get("date")
    assert date == "2022-09-08T22:45Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?lang=en&limit=50&dates=20260320-20260322&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == None


#    assert await entry.async_unload(hass)
#    await hass.async_block_till_done()


async def test_setup_platform(hass):
    """test platform setup"""

# Mock implementation of async_add_entities callback
    entity_list = []
    def mock_async_add_entities_callback(entities: list[Any], update_before_add: bool = False) -> None:
        """Mock implementation of the async_add_entities callback."""
        # Simulate async_add_entities callback behavior
        entity_list.extend(entities)
        print(f"Adding entities: {entity_list}")

    for test in PLATFORM_TEST_DATA:
        await async_setup_platform(
            hass,
            test[0],
            mock_async_add_entities_callback,
            discovery_info=None,
        )

        assert (DOMAIN in hass.data) == test[1]
