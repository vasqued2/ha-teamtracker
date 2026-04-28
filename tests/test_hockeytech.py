""" Test TeamTracker Sensor """
from freezegun import freeze_time
import asyncio
import threading
from collections.abc import Generator # <-- New import
import logging
import json
import aiofiles

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from typing import Any
from custom_components.teamtracker.const import DOMAIN
from custom_components.teamtracker.sensor import async_setup_platform
from tests.const import CONFIG_DATA, PLATFORM_TEST_DATA
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from unittest.mock import AsyncMock, patch


@pytest.fixture
async def mock_call_hockeytech_api(hass):
    """Global fixture to mock the HockeyTech API and return local JSON data."""
    
    async def _get_mock_ht_api_data(hass, sensor_name, team_id, url, file_override=False):
        """Read FILE_NAME instead of calling the API."""

        if sensor_name == "api_error":
            return None

        FILE_NAME = "tests/tt/hockeytech-scorebar.json"

        try:
            with open(f"{FILE_NAME}", "r") as f:
                data = json.load(f)
                return data
        except FileNotFoundError:
            return None

    # Patch the actual utility function
    with patch("custom_components.teamtracker.hockeytech.async_call_hockeytech_api", new_callable=AsyncMock) as mock_ht:
        mock_ht.side_effect = _get_mock_ht_api_data
        yield mock_ht


@freeze_time("2026-03-21 10:00:00")
async def test_hockeytech(hass, mock_call_hockeytech_api, mocker):
    """ Simple test for HockeyTech """

    SAMPLE_DATA = {
        "league_id": "XXX",
        "team_id": "BOS",
        "name": "test_sample",
        "sport_path": "hockey",
        "league_path": "PWHL",
        "timeout": 120,
        "conference_id": "9999",
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sample",
        data=SAMPLE_DATA,
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

    sensor_state = hass.states.get("sensor.test_sample")

    assert sensor_state.state == "PRE"
    team_abbr = sensor_state.attributes.get("team_abbr")
    assert team_abbr == "BOS"
    sport = sensor_state.attributes.get("sport")
    assert sport == "hockey"
    league_name = sensor_state.attributes.get("league_name")
    assert league_name == ""
    event_name = sensor_state.attributes.get("event_name")
    assert event_name == "OTT @ BOS"
    date = sensor_state.attributes.get("date")
    assert date == "2026-04-30T23:00Z"
    api_url = sensor_state.attributes.get("api_url")
    assert api_url == "pwhl.hockeytech.com/scorebar"
    api_message = sensor_state.attributes.get("api_message")
    assert api_message == None
