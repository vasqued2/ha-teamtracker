""" Test TeamTracker Sensor """

import pytest
from unittest.mock import Mock, patch
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.teamtracker.const import DOMAIN
from custom_components.teamtracker.sensor import TeamTrackerScoresSensor
from tests.const import CONFIG_DATA


@pytest.fixture(autouse=False)
def expected_lingering_timers() -> bool:
    """"  Temporary ability to bypass test failures due to lingering timers.
        Parametrize to True to bypass the pytest failure.
        @pytest.mark.parametrize("expected_lingering_timers", [True])
        This should be removed when all lingering timers have been cleaned up.
    """
    return False


#@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_sensor(hass, mocker):
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

    assert await entry.async_unload(hass)
    await hass.async_block_till_done()

#import pytest
#from mock import patch
#
#from custom_component.sensor import TeamTrackerScoresSensor


@pytest.mark.asyncio
async def test_team_tracker_scores_sensor():
    """Test the TeamTrackerScoresSensor class."""

    # create a mock HomeAssistant object
    hass = Mock()

    # create a mock ConfigEntry object
    config_entry = Mock()

    # create a mock Coordinator object
    coordinator = Mock()

    coordinator.data = {
        "sport": "football",
        "league": "premier-league",
        "league_logo": "https://example.com/league-logo.png",
        "team_abbr": "CLE",
        "opponent_abbr": "HOU",

        "event_name": "2023 NBA Playoffs",
        "date": "2023-04-23",
        "kickoff_in": "12:00 PM",
        "venue": "Rocket Mortgage FieldHouse",
        "location": "Cleveland, OH",
        "tv_network": "ABC",
        "odds": "CLE -5",
        "overunder": 210,

        "team_name": "Cleveland Cavaliers",
        "team_id": "123456",
        "team_record": "48-34",
        "team_rank": 6,
        "team_homeaway": "home",
        "team_logo": "https://example.com/team-logo.png",
        "team_colors": ["#1E1E1E", "#E91E63"],
        "team_score": 80,
        "team_win_probability": 0.90,
        "team_timeouts": 2,

        "opponent_name": "Houston Rockets",
        "opponent_id": "789012",
        "opponent_record": "34-48",
        "opponent_rank": 14,
        "opponent_homeaway": "away",
        "opponent_logo": "https://example.com/opponent-logo.png",
        "opponent_colors": ["#00C853", "#000000"],
        "opponent_score": 60,
        "opponent_win_probability": 0.10,
        "opponent_timeouts": 3,

        "quarter": 4,
        "clock": "1:00",
        "possession": "CLE",
        "last_play": "James dunks",
        "down_distance_text": "3rd and 10",

        "outs": 0,
        "balls": 2,
        "strikes": 0,
        "on_first": False,
        "on_second": False,
        "on_third": False,

        "team_shots_on_target": 10,
        "team_total_shots": 20,
        "opponent_shots_on_target": 8,
        "opponent_total_shots": 15,

        "team_sets_won": 2,
        "opponent_sets_won": 1,

        "last_update": "2023-04-23T12:00:00Z",
        "api_message": None,
    }

    # assign the Coordinator to the HomeAssistant data object
    hass.data = {"team_tracker_scores": {config_entry.entry_id: {"coordinator": coordinator}}}

    # create the sensor object
    sensor = TeamTrackerScoresSensor(hass, config_entry)

    # Set the coordinator on the sensor.
    sensor.coordinator = coordinator

    # Check the initial state of the sensor.
    assert sensor.state == "PRE"
    assert sensor.extra_state_attributes == {}
    assert sensor.available is False

    # Update the coordinator.
    coordinator.update()

    # Check the updated state of the sensor.
    assert sensor.state == "80-60"
    assert sensor.extra_state_attributes == {
        "sport": "football",
        "league": "premier-league",
        "league_logo": "https://example.com/league-logo.png",
        "team_abbr": "CLE",
        "opponent_abbr": "HOU",

        "event_name": "2023 NBA Playoffs",
        "date": "2023-04-23",
        "kickoff_in": "12:00 PM",
        "venue": "Rocket Mortgage FieldHouse",
        "location": "Cleveland, OH",
        "tv_network": "ABC",
        "odds": "CLE -5",
        "overunder": 210,

        "team_name": "Cleveland Cavaliers",
        "team_id": "123456",
        "team_record": "48-34",
        "team_rank": 6,
        "team_homeaway": "home",
        "team_logo": "https://example.com/team-logo.png",
        "team_colors": ["#1E1E1E", "#E91E63"],
        "team_score": 80,
        "team_win_probability": 0.90,
        "team_timeouts": 2,

        "opponent_name": "Houston Rockets",
        "opponent_id": "789012",
        "opponent_record": "34-48",
        "opponent_rank": 14,
        "opponent_homeaway": "away",
        "opponent_logo": "https://example.com/opponent-logo.png",
        "opponent_colors": ["#00C853", "#000000"],
        "opponent_score": 60,
        "opponent_win_probability": 0.10,
        "opponent_timeouts": 3,

        "quarter": 4,
        "clock": "1:00",
        "possession": "CLE",
        "last_play": "James dunks",
        "down_distance_text": "3rd and 10",

        "outs": 0,
        "balls": 2,
        "strikes": 0,
        "on_first": False,
        "on_second": False,
        "on_third": False,

        "team_shots_on_target": 10,
        "team_total_shots": 20,
        "opponent_shots_on_target": 8,
        "opponent_total_shots": 15,

        "team_sets_won": 2,
        "opponent_sets_won": 1,

        "last_update": "2023-04-23T12:00:00Z",
        "api_message": None,
    }

