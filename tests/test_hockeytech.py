""" Test TeamTracker Sensor """
from freezegun import freeze_time
import asyncio
import threading
from collections.abc import Generator # <-- New import
import logging
import json
import aiofiles
from yarl import URL

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from typing import Any
from custom_components.teamtracker.const import (
    DOMAIN,
    USER_AGENT,
)
from custom_components.teamtracker.hockeytech import (
    HOCKEYTECH_BASE_URL,
    HOCKEYTECH_LEAGUES,
    HOCKEYTECH_TEAM_COLORS,
)
from custom_components.teamtracker.sensor import async_setup_platform
from tests.const import CONFIG_DATA, PLATFORM_TEST_DATA
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from unittest.mock import AsyncMock, patch

HOCKEYTECH_DATA = [
    {
        "league_id": "XXX",
        "team_id": "BOS",
        "name": "test_pre",
        "sport_path": "hockeytech",
        "league_path": "PWHL",
        "timeout": 120,
        "conference_id": "9999",
    },
    {
        "league_id": "XXX",
        "team_id": "FW",
        "name": "test_in",
        "sport_path": "hockeytech",
        "league_path": "ECHL",
        "timeout": 120,
        "conference_id": "9999",
    },
    {
        "league_id": "XXX",
        "team_id": "SEA",
        "name": "test_post",
        "sport_path": "hockeytech",
        "league_path": "PWHL",
        "timeout": 120,
        "conference_id": "9999",
    },
    {
        "league_id": "XXX",
        "team_id": "SEA",
        "name": "api_error_invalid_league",  # Invalid league will result in a bad URL and generate an API Error
        "sport_path": "hockeytech",
        "league_path": "INVALID_LEAGUE_PATH",
        "timeout": 120,
        "conference_id": "9999",
    },
    {
        "league_id": "XXX",
        "team_id": "INVALID_TEAM_ID",
        "name": "test_invalid_team",   # Invalid team will use correct league API but won't find team
        "sport_path": "hockeytech",
        "league_path": "PWHL",
        "timeout": 120,
        "conference_id": "9999",
    },

]



@freeze_time("2026-03-21 20:00:00")
@pytest.mark.parametrize("ht", HOCKEYTECH_DATA, ids=lambda x: x["name"])
async def test_hockeytech(hass, snapshot, mock_call_hockeytech_api, mocker, ht):
    """  
        This regression tests attributes for all the hockeytech API
            It runs a test for state PRE, IN, and POST
            To set a new snapshot baseline: pytest --snapshot-update
    """

    SAMPLE_DATA = ht

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

    sensor_state = hass.states.get(f"sensor.{ht['name']}")
    assert sensor_state is not None

    attributes = dict(sensor_state.attributes)

    attributes.pop("kickoff_in", None)
    attributes.pop("last_update", None)

    assert attributes == snapshot