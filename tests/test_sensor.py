"""Test NFL Sensor"""

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamtracker.const import DOMAIN

from tests.const import CONFIG_DATA


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Temporary ability to bypass test failures.
    Parametrize to True to bypass the pytest failure.
    @pytest.mark.parametrize("expected_lingering_timers", [True])
    This should be removed when all lingering timers have been cleaned up.
    """
    return True

    
@pytest.mark.usefixtures("expected_lingering_timers")
async def test_sensor(hass, mocker):
    """ Make sure sensor gets added """

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NFL",
        data=CONFIG_DATA,
    )

    mocker.patch("locale.getlocale", return_value=("en", 0))

    #    contents = "{}"
    #    mocker.patch('aiofiles.open', return_value=mocker.mock_open(read_data=contents).return_value)

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "teamtracker" in hass.config.components
