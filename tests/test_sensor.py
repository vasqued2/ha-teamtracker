""" Test TeamTracker Sensor """

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.teamtracker.const import DOMAIN
from custom_components.teamtracker.sensor import TeamTrackerScoresSensor
from tests.const import CONFIG_DATA

from homeassistant.core import HomeAssistant

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



@pytest.fixture
def hass():
    return HomeAssistant()

def test_team_tracker_scores_sensor(hass):
    entry = {
        'entry_id': 'test_entry_id',
        'data': {
            'sport_path': 'football',
            'name': 'Test Sensor',
        },
    }

    sensor = TeamTrackerScoresSensor(hass, entry)
    assert sensor._name == 'Test Sensor'
    assert sensor._icon == 'default_icon'
    assert sensor._state == 'PRE'
    assert sensor._sport == None
    assert sensor._league == None
    assert sensor._league_logo == None
    assert sensor._team_abbr == None
    assert sensor._opponent_abbr == None
    assert sensor._event_name == None
    assert sensor._date == None
    assert sensor._kickoff_in == None
    assert sensor._venue == None
    assert sensor._location == None
    assert sensor._tv_network == None
    assert sensor._odds == None
    assert sensor._overunder == None
    assert sensor._team_name == None
    assert sensor._team_id == None
    assert sensor._team_record == None
    assert sensor._team_rank == None
    assert sensor._team_homeaway == None
    assert sensor._team_logo == None
    assert sensor._team_colors == None
    assert sensor._team_score == None
    assert sensor._team_win_probability == None
    assert sensor._team_timeouts == None
    assert sensor._opponent_name == None
    assert sensor._opponent_id == None
    assert sensor._opponent_record == None
    assert sensor._opponent_rank == None
    assert sensor._opponent_homeaway == None
    assert sensor._opponent_logo == None
    assert sensor._opponent_colors == None
    assert sensor._opponent_score == None
    assert sensor._opponent_win_probability == None
    assert sensor._opponent_timeouts == None
    assert sensor._quarter == None
    assert sensor._clock == None
    assert sensor._possession == None
    assert sensor._last_play == None
    assert sensor._down_distance_text == None
    assert sensor._outs == None
    assert sensor._balls == None
    assert sensor._strikes == None
    assert sensor._on_first == None
    assert sensor._on_second == None
    assert sensor._on_third == None
    assert sensor._team_shots_on_target == None
    assert sensor._team_total_shots == None
    assert sensor._opponent_shots_on_target == None
    assert sensor._opponent_total_shots == None
    assert sensor._team_sets_won == None
    assert sensor._opponent_sets_won == None
    assert sensor._last_update == None
    assert sensor._api_message == None
