""" Tests for TeamTracker """
import json
import logging
import aiofiles
import datetime

from unittest.mock import patch, MagicMock, AsyncMock
from freezegun import freeze_time
import arrow
from datetime import date

from custom_components.teamtracker import TeamTrackerDataUpdateCoordinator
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.teamtracker.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from tests.const import CONFIG_DATA, CONFIG_DATA2, CONFIG_DATA3, CONFIG_DATA4

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
@freeze_time("2026-03-21 10:00:00")
async def test_all_leagues_cold_start(hass):
    """Test Case 1: Cold start falls through to file-based discovery."""
#
#   Reset Caches
#
    TeamTrackerDataUpdateCoordinator.data_cache = {}
    TeamTrackerDataUpdateCoordinator.last_update = {}
    TeamTrackerDataUpdateCoordinator.all_team_cache = {}

#
#   Set up entry
#
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA3,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

#
# Validate sensor state and attributes based on CONFIG_DATA3
#

    sensor_state = hass.states.get("sensor.test_tt_all_test99")

    assert sensor_state.state == "POST"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "CLB"
    sport = sensor_state.attributes.get("sport")
    assert sport == "soccer"
    league = sensor_state.attributes.get("league")
    assert league == "MLS"
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == "MLS"
    event_name = sensor_state.attributes.get("event_name")
    assert event_name == "CLB @ TOR"
    date = sensor_state.attributes.get("date")
    assert date == "2026-03-21T17:00Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?lang=en&limit=50&dates=20260319-20260321&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == "Cached data" # data refresh is called twice on setup, so 2nd time uses cache
#
# Validate the cache's are now populated
#

    data_cache = TeamTrackerDataUpdateCoordinator.data_cache
    all_team_cache = TeamTrackerDataUpdateCoordinator.all_team_cache

    assert isinstance(data_cache, dict)
    assert len(data_cache) > 0
    assert isinstance(all_team_cache, dict)
    assert len(all_team_cache) > 0



@freeze_time("2026-03-21 10:00:00")
async def test_all_leagues_data_cache_hit(hass, mock_call_espn_api):
    """Test Case 2: Use internal data_cache to skip API calls during a refresh."""
    
    # 1. INITIAL SETUP 
    # This triggers the automatic first update (Cold Start)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA3,
    )
    entry.add_to_hass(hass)

    # Ensure caches are empty before setup
    TeamTrackerDataUpdateCoordinator.data_cache.clear()
    TeamTrackerDataUpdateCoordinator.last_update.clear()

    # Setup the entry - this will call the API 3 times in the background
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    lu = TeamTrackerDataUpdateCoordinator.last_update
    dc = TeamTrackerDataUpdateCoordinator.data_cache

    data_cache = TeamTrackerDataUpdateCoordinator.data_cache
    last_update = TeamTrackerDataUpdateCoordinator.last_update
    all_team_cache = TeamTrackerDataUpdateCoordinator.all_team_cache

    assert isinstance(data_cache, dict)
    assert len(data_cache) > 0
    assert isinstance(last_update, dict)
    assert len(last_update) > 0
    assert isinstance(all_team_cache, dict)
    assert len(all_team_cache) > 0



    # 3. DEFINE THE SNITCH
    def mock_snitch(url):
        import traceback
        print(f"\n[MOCK BREAKPOINT] LEAK DETECTED! Called with URL: {url}")
        traceback.print_stack() 
        breakpoint()
        return {} 

    # 4. PATCH AND REFRESH
    # We only patch the coordinator AFTER the setup is done
    with patch("custom_components.teamtracker.async_call_espn_api", side_effect=mock_snitch) as snitch_espn_api:

        # This is the second update attempt
        await coordinator.async_refresh()

        # 5. ASSERTIONS
        # This must be 0. If it's > 0, the snitch will print the stack trace 
        # showing exactly which line in the coordinator "leaked" the call.
        assert snitch_espn_api.call_count == 0
        
        # Verify the sensor state reflects it used the cache
        sensor_state = hass.states.get("sensor.test_tt_all_test99")
        assert sensor_state.attributes.get("api_message") == "Cached data"



@freeze_time("2026-03-21 10:00:00")
async def test_all_leagues_all_team_cache_hit(hass, mock_call_espn_api):
    """Test Case 3: Use internal all_team_cache to skip API call for league_name."""
    
    # 1. INITIAL SETUP 
    # This triggers the automatic first update (Cold Start)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA3,
    )
    entry.add_to_hass(hass)

    # Ensure caches are empty before setup
    TeamTrackerDataUpdateCoordinator.data_cache.clear()
    TeamTrackerDataUpdateCoordinator.last_update.clear()

    # Setup the entry - this will call the API 3 times in the background
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    data_cache = TeamTrackerDataUpdateCoordinator.data_cache
    last_update = TeamTrackerDataUpdateCoordinator.last_update
    all_team_cache = TeamTrackerDataUpdateCoordinator.all_team_cache

    assert isinstance(data_cache, dict)  # key="soccer:all:9999:en:183"
    assert len(data_cache) > 0  
    assert isinstance(last_update, dict)  # key="soccer:all:9999:en:183"
    assert len(last_update) > 0
    assert isinstance(all_team_cache, dict) # key="soccer:all:183"
    assert len(all_team_cache) > 0

    sensor_state = hass.states.get("sensor.test_tt_all_test99")
    assert sensor_state.state == "POST"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "CLB"
    sport = sensor_state.attributes.get("sport")
    assert sport == "soccer"
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == "MLS"
    event_name = sensor_state.attributes.get("event_name")
    assert event_name == "CLB @ TOR"
    date = sensor_state.attributes.get("date")
    assert date == "2026-03-21T17:00Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?lang=en&limit=50&dates=20260319-20260321&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == "All-league: 1 scoreboard call(s), dates=20260319-20260321" # Need to track down why it's cached data

# 2. EXPIRE THE DATA CACHE
    # Clear out the data_cache.
    TeamTrackerDataUpdateCoordinator.data_cache.clear()
    TeamTrackerDataUpdateCoordinator.last_update.clear()

    # Update the league_name in the all_team_cache so we know we are reading it
    league_key = "soccer:all:183"
    if league_key in TeamTrackerDataUpdateCoordinator.all_team_cache:
        comp_dict = TeamTrackerDataUpdateCoordinator.all_team_cache[league_key]["id_to_competition"]
        for team_id in comp_dict:
            comp_dict[team_id] = "Cached MLS"

    # This is the second update attempt
    await coordinator.async_refresh()

    # 5. ASSERTIONS
    
    # Verify the sensor state reflects it used the cache
    sensor_state = hass.states.get("sensor.test_tt_all_test99")

    state = sensor_state.state
    assert state == "POST"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "CLB"
    sport = sensor_state.attributes.get("sport")
    assert sport == "soccer"
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == "Cached MLS"                          # Confirm league name came from cache
    event_name = sensor_state.attributes.get("event_name")
    assert event_name == "CLB @ TOR"
    date = sensor_state.attributes.get("date")
    assert date == "2026-03-21T17:00Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?lang=en&limit=50&dates=20260319-20260321&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == "All-league: 1 scoreboard call(s), dates=20260319-20260321" # Confirm "all" league API was called



    
#@pytest.mark.parametrize("expected_lingering_timers", [True])
@freeze_time("2026-03-21 10:00:00")
async def test_all_leagues_cold_start(hass, mock_call_espn_api):
    """Test Case 1: Cold start falls through to file-based discovery."""
#
#   Reset Caches
#
    TeamTrackerDataUpdateCoordinator.data_cache = {}
    TeamTrackerDataUpdateCoordinator.last_update = {}
    TeamTrackerDataUpdateCoordinator.all_team_cache = {}

#
#   Set up entry
#
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA3,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

#
# Validate sensor state and attributes based on CONFIG_DATA3
#

    sensor_state = hass.states.get("sensor.test_tt_all_test99")

    assert sensor_state.state == "POST"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "CLB"
    sport = sensor_state.attributes.get("sport")
    assert sport == "soccer"
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == "MLS"
    event_name = sensor_state.attributes.get("event_name")
    assert event_name == "CLB @ TOR"
    date = sensor_state.attributes.get("date")
    assert date == "2026-03-21T17:00Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?lang=en&limit=50&dates=20260319-20260321&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == "All-league: 1 scoreboard call(s), dates=20260319-20260321"
#
# Validate the cache's are now populated
#

    data_cache = TeamTrackerDataUpdateCoordinator.data_cache
    all_team_cache = TeamTrackerDataUpdateCoordinator.all_team_cache

    assert isinstance(data_cache, dict)
    assert len(data_cache) > 0
    assert isinstance(all_team_cache, dict)
    assert len(all_team_cache) > 0


    
#@pytest.mark.parametrize("expected_lingering_timers", [True])
@freeze_time("2026-03-21 10:00:00")
async def test_all_leagues_team_abbr(hass):
    """Test Case 4: Cold start using team abbreviation instead of Team ID number."""
    """  Special "all" league processing should be skipped when Team ID is not an integer """
#
#   Reset Caches
#
    TeamTrackerDataUpdateCoordinator.data_cache = {}
    TeamTrackerDataUpdateCoordinator.last_update = {}
    TeamTrackerDataUpdateCoordinator.all_team_cache = {}

#
#   Set up entry
#
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA4,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

#
# Validate sensor state and attributes based on CONFIG_DATA3
#

    sensor_state = hass.states.get("sensor.test_tt_all_test99")

    assert sensor_state.state == "POST"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "CLB"
    sport = sensor_state.attributes.get("sport")
    assert sport == "soccer"
    league = sensor_state.attributes.get("league")
    assert league == "XXX" # Abbreviation should go through old processing
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == "" # Abbreviation should go through old processing
    event_name = sensor_state.attributes.get("event_name")
    assert event_name == "CLB @ TOR"
    date = sensor_state.attributes.get("date")
    assert date == "2026-03-21T17:00Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "http://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?lang=en&limit=50&dates=20260320-20260326&groups=9999"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == None
#
# Validate the cache's are now populated
#

    data_cache = TeamTrackerDataUpdateCoordinator.data_cache
    all_team_cache = TeamTrackerDataUpdateCoordinator.all_team_cache

    assert isinstance(data_cache, dict)
    assert len(data_cache) > 0
    assert isinstance(all_team_cache, dict)
    assert len(all_team_cache) == 0 # all_team_cache should remain 0 because all league processing skipped
