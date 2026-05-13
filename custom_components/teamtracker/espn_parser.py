from __future__ import annotations

import arrow
import logging
from typing import TYPE_CHECKING

from .base_parser import BaseSportParser
from .clear_values import async_clear_values
from .const import (
    DEFAULT_LOGO
)
from .event import async_process_event
from .utils import is_integer
_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class EspnParser(BaseSportParser):
    """Class to parse responses in ESPN JSON format."""

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        # Define the attributes that must be available on all providers
        super().__init__(coordinator)
        self._coordinator = coordinator


    #
    #  async_update_values()
    #
    async def async_parse_data(self, data) -> dict:
        """Updates sensor values using data returned by API or in cache"""

        if not self._coordinator:
            return{}

        sensor_name = self._coordinator.name
        team_id = self._coordinator.team_id.upper()

        league_id = self._coordinator.league_id.upper()
        team_id = self._coordinator.team_id.upper()
        lang = self._coordinator.get_lang()

        # Populate base values that do not need API data
        values = {}
        values = await async_clear_values()
        if self._coordinator.sport_path.lower() == "hockeytech":
            values["sport"] = "hockey"
        else:
            values["sport"] = self._coordinator.sport_path
        values["sport_path"] = self._coordinator.sport_path
        values["league"] = league_id
        values["league_path"] = self._coordinator.league_path
        values["league_logo"] = DEFAULT_LOGO
        values["team_abbr"] = team_id
        values["state"] = "NOT_FOUND"
        values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
        values["private_fast_refresh"] = False
        values["api_url"] = self._coordinator.api_url

        # If there was an error (i.e. 404) w/ the API call...
        if data is None:
            values["api_message"] = "API error, no data returned"
            _LOGGER.warning(
                "%s: API did not return any data for team '%s'", sensor_name, team_id
            )
            return values

        # When league_path is "all", parser needs league_map{} to do manual lookup
        league_map = {}
        if (self._coordinator.league_path) == "all":
            cache_key = f"{self._coordinator.sport_path}:{self._coordinator.league_path}:{self._coordinator.team_id}"
            team_cache = self._coordinator.all_team_cache.get(cache_key) # Using class variable
            if team_cache:
                league_map = team_cache.get("league_map", {})

        values = await async_process_event(
            values,
            sensor_name,
            data,
            self._coordinator.sport_path,
            league_id,
            DEFAULT_LOGO,
            team_id,
            league_map,
            lang,
        )

        # If NOT_FOUND, try to get abbr w/ another API to make message easier to read
        if (values["state"] == "NOT_FOUND" and 
            is_integer(team_id)
        ):
            response = await self._coordinator.provider.async_fetch_team_data(self._coordinator.hass, self._coordinator.sport_path, self._coordinator.league_path)
            teams = response["data"]
            if teams:
                team_abbr = next(
                    (team["abbreviation"] for team in teams if team["id"] == team_id),
                    None,
                )
            else:
                team_abbr = None

            values["team_id"] = team_id
            if team_abbr:
                values["team_abbr"] = team_abbr

        return values
