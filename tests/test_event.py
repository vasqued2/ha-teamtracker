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

    values = TeamTrackerValues()
    values.sport = t["sport"]
    values.league = t["league"]
    values.league_logo = DEFAULT_LOGO
    values.team_abbr = t["team_abbr"]
    values.state = "NOT_FOUND"
    values.last_update = DEFAULT_LAST_UPDATE
    values.private_fast_refresh = False

    sensor_name = t["sensor_name"]
    sport_path = values.sport
    league_id = values.league
    team_id = values.team_abbr
    lang = "en"
    league_map= {}

    _LOGGER.debug("%s: calling async_process_event()", sensor_name)

    parser = EspnParser()
    parser.setup(sensor_name, sport_path, league_id, team_id)

    assert t["frozen_time"] is not None

    with freeze_time(t["frozen_time"]):
        values = await parser.async_parse_response(
            values,
            data,
            league_map,
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