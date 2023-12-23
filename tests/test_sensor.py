""" Test TeamTracker Sensor """

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from typing import Any
from custom_components.teamtracker.const import DOMAIN
from custom_components.teamtracker.sensor import async_setup_platform
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

class SensorConfigType(dict):
    """Wrapper class to be able to add attributes on a dict."""

    def __init__(self, data=None, entry_id=None, **kwargs):
        super().__init__(**kwargs)
        self.data = data
        self.entry_id = entry_id

# Create the mock object
sensor_config = SensorConfigType(
    platform='teamtracker',
    league_id="MLB",
    team_id="MIA",
    name="test_tt_all_test01",
    conference_id="9999",
    entry_id={},
    data={}
)


# Mock implementation of async_add_entities callback
entity_list = []
async def mock_async_add_entities_callback(entities: list[Any], update_before_add: bool = False) -> None:
    """Mock implementation of the async_add_entities callback."""
    # Simulate async_add_entities callback behavior
    entity_list.extend(entities)
    print(f"Adding entities: {entity_list}")



async def test_setup_platform(hass):
    """test platform setup"""

    await async_setup_platform(
        hass,
        sensor_config,
        mock_async_add_entities_callback,
        discovery_info=None,
    )

    assert DOMAIN in hass.data