""" Tests for TeamTracker """

from freezegun import freeze_time
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.teamtracker.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from tests.const import CONFIG_DATA, CONFIG_DATA2, CONFIG_DATA5, CONFIG_DATA6
import logging
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
async def test_setup_entry(
    hass,
):
    """ test setup """

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA,
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

    assert sensor_state.state == "NOT_FOUND"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "BOS"
    sport = sensor_state.attributes.get("sport")
    assert sport == "basketball"

#    assert await entry.async_unload(hass)
#    await hass.async_block_till_done()


#@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_setup_NOT_FOUND_api_error(
    hass,
    mock_espn_api
):
    """ Test when team_id is a digit and is NOT_FOUND, should eventually set abbr to abbr instead of ID """

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA5,
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

    sensor_state = hass.states.get("sensor.test_tt_all_test99")

    assert sensor_state.state == "NOT_FOUND"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "195"    # Internet down so can't look up team_abbr
    sport = sensor_state.attributes.get("sport")
    assert sport == "football"
#    date = sensor_state.attributes.get("date")
#    assert date == "2022-09-08T22:45Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=15"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == "API error, no data returned" 

#    assert await entry.async_unload(hass)
#    await hass.async_block_till_done()


#@pytest.mark.parametrize("expected_lingering_timers", [True])
@freeze_time("2026-03-21 10:00:00")
async def test_setup_NOT_FOUND_no_team_id(
    hass,
    mock_espn_api
):
    """ Test when team_id is a digit and is NOT_FOUND, should eventually set abbr to abbr instead of ID """

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA6,
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

    sensor_state = hass.states.get("sensor.test_tt_all_test99")

    assert sensor_state.state == "NOT_FOUND"
    team_id = sensor_state.attributes.get("team_id")
    assert team_id == "195"    # Populate Team ID w/ provided team_id
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "OSU"    # Change to team abbreviation (OSU)
    sport = sensor_state.attributes.get("sport")
    assert sport == "football"
    date = sensor_state.attributes.get("date")
    assert date == None
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?lang=en&limit=50&dates=20260320-20260619&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == "No competition scheduled for '195' between 2022-09-08T18:20Z and 2024-08-04T04:00Z"


#    assert await entry.async_unload(hass)
#    await hass.async_block_till_done()


#@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_setup_recreate_blank_api_url(
    hass,
):
    """ test setup """

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

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
    date = sensor_state.attributes.get("date")
    assert date == "2022-09-08T22:45Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?lang=en&limit=50&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == None

    await coordinator.async_refresh()

    assert sensor_state.state == "PRE"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "MIA"
    sport = sensor_state.attributes.get("sport")
    assert sport == "baseball"
    date = sensor_state.attributes.get("date")
    assert date == "2022-09-08T22:45Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?lang=en&limit=50&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == None


#    assert await entry.async_unload(hass)
#    await hass.async_block_till_done()


#@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_unload_entry(hass):
    """ test unload """

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA2,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0

    assert await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0

    assert await entry.async_unload(hass)
    await hass.async_block_till_done()