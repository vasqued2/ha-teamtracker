""" Tests for TeamTracker """

import logging
import os
import shutil
from unittest.mock import patch

from freezegun import freeze_time
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamtracker.const import DOMAIN, LOCAL_OVERRIDE_FILE
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

RELOAD_DATA = {
        "league_id": "XXX",
        "team_id": "FW",
        "name": "test_tt_all_test01",
        "sport_path": "hockeytech",
        "league_path": "chl",
        "timeout": 120,
        "conference_id": "9999",
    }

CALL_API_DATA = {
    "league_id": "MLB",
    "team_id": "MIA",
    "name": "test_tt_all_test01",
    "timeout": 120,
    "conference_id": "9999",
}

_LOGGER = logging.getLogger(__name__)

@pytest.fixture(autouse=False)
def expected_lingering_timers() -> bool:
    """  Temporary ability to bypass test failures due to lingering timers.
    Parametrize to True to bypass the pytest failure.
    @pytest.mark.parametrize("expected_lingering_timers", [True])
    This should be removed when all lingering timers have been cleaned up.
    """
    return False


#@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_reload_overrides_service(
    hass,
    mock_call_hockeytech_api
):
    """Test initial entry setup and subsequent service call"""

    #
    #  Confirm the TEST_OVERRIDE_FILE exists and delete the local override file
    #
    TEST_OVERRIDE_FILE = "tests/tt/test_teamtracker_overrides.json"
    assert os.path.exists(TEST_OVERRIDE_FILE)

    custom_file = hass.config.path(LOCAL_OVERRIDE_FILE)
    if os.path.exists(custom_file):
        os.remove(custom_file)

    #
    # Set up initial entry
    #

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=RELOAD_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    #
    # Validate sensor state and attributes based on CONFIG_DATA
    #

    sensor_state = hass.states.get("sensor.test_tt_all_test01")

    assert sensor_state.state == "IN"
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == "Canadian Hockey League"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "FW"
    sport = sensor_state.attributes.get("sport")
    assert sport == "hockey"

    #
    #  Copy TEST_OVERRIDE_FILE to LOCAL_OVERRIDE_FILE and rerun test
    #
    custom_file_path = hass.config.path(LOCAL_OVERRIDE_FILE)
    os.makedirs(os.path.dirname(custom_file_path), exist_ok=True)
    shutil.copy(TEST_OVERRIDE_FILE, custom_file_path)

    #
    # Call service to change sensor
    #

    await hass.services.async_call(
        domain="teamtracker",
        service="reload_overrides",
        target={
            "entity_id": [
                "sensor.test_tt_all_test01",
            ]
        },
        blocking=True
    )

    # Refresh data

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_refresh()

    #
    # Validate league_name was changed by the override
    #

    sensor_state = hass.states.get("sensor.test_tt_all_test01")

    assert sensor_state.state == "IN"
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == "Override League Name"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "FW"
    sport = sensor_state.attributes.get("sport")
    assert sport == "hockey"


#@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_call_api_service(
    hass,
    mock_call_espn_api
):
    """Test initial entry setup and subsequent service call"""

    #
    # Set up initial entry
    #

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CALL_API_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    #
    # Validate sensor state and attributes based on CONFIG_DATA
    #

    sensor_state = hass.states.get("sensor.test_tt_all_test01")

    assert sensor_state.state == "PRE"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "MIA"
    sport = sensor_state.attributes.get("sport")
    assert sport == "baseball"

    #
    # Call service to change sensor
    #

    await hass.services.async_call(
        domain="teamtracker",
        service="call_api",
        service_data={
            "sport_path": "basketball",
            "league_path": "nba",
            "team_id": "bos"
        },
        target={
            "entity_id": [
                "sensor.test_tt_all_test01",
            ]
        },
        blocking=True
    )

    #
    # Validate sensor state and attributes changed based on API call
    #

    sensor_state = hass.states.get("sensor.test_tt_all_test01")

    assert sensor_state.state == "POST"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "BOS"
    sport = sensor_state.attributes.get("sport")
    assert sport == "basketball"

