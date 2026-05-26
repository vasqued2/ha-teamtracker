import json
import logging

import aiofiles
from freezegun import freeze_time
import pytest

from custom_components.teamtracker.const import (
    DEFAULT_KICKOFF_IN,
    DEFAULT_LAST_UPDATE,
    DEFAULT_LOGO,
)
from custom_components.teamtracker.models import TeamTrackerValues
from custom_components.teamtracker.parse_espn import EspnParser

from tests.const import TEST_DATA

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize("t", TEST_DATA, ids=lambda x: x["sensor_name"])
async def test_event(hass, snapshot, t):
    """  
        This regression tests attributes for all of supported sports, leagues, and game states
            It runs a test for each case in TEST_DATA and compares it to the snapshot
            To set a new snapshot baseline: pytest --snapshot-update
    """

    async with aiofiles.open("tests/tt/all.json", mode="r") as f:
        contents = await f.read()
    data = json.loads(contents)

    assert data is not None

    sensor_name = t["sensor_name"]
    sport_path = t["sport"]
    league_path = t["league"].lower()
    league_id = t["league"]
    team_id = t["team_abbr"]
    lang = "en"
    league_map= {}

    _LOGGER.debug("%s: calling async_process_event()", sensor_name)

    parser = EspnParser(None)
    parser.setup(sensor_name, sport_path, league_path, league_id, team_id)

    assert t["frozen_time"] is not None

    url = "url"
    timestamp = DEFAULT_LAST_UPDATE
    provider_response = {
        "data": data,
        "url": url,
        "timestamp": timestamp
    }
    with freeze_time(t["frozen_time"]):
        values = parser.parse_response(
            provider_response,
            lang,
        )

    assert values

    # Normalize dynamic fields
    values.api_url = None
    values.sport_path = None
    values.league_path = None
    values.kickoff_in = DEFAULT_KICKOFF_IN

    values_dict = values.to_dict_all_attr()
    assert values_dict == snapshot