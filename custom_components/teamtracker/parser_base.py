""" Base class for all parsers """
from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import TYPE_CHECKING

from .const import DEFAULT_LOGO
from .models import TeamTrackerValues
from .utils import is_integer

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class BaseSportParser(ABC):
    """Base class for all sport data providers."""

    def __init__(self) -> None:
        # Define the attributes that must be available on all providers
        self._values = TeamTrackerValues()
        self._sensor_name = ""
        self._sport_path = ""
        self._league_path = ""
        self._league_id = ""
        self._default_logo = DEFAULT_LOGO
        self._team_id = ""

    #
    #  initialize_values()
    #    Set sensor attributes that do not rely on the API
    #
    def initialize_sensor_values(self, provider_response) -> bool:

        data = provider_response["data"]
        url = provider_response["url"]
        timestamp = provider_response["timestamp"]

        self._values = TeamTrackerValues()

        self._values.state = "NOT_FOUND"
        self._values.sport = self._sport_path
        self._values.sport_path = self._sport_path
        self._values.league = self._league_id
        self._values.league_path = self._league_path
        self._values.league_logo = self._default_logo
        self._values.team_abbr = self._team_id
        self._values.last_update = timestamp
        self._values.private_fast_refresh = False
        self._values.api_url = url
        self._values.api_message = None

        if data is None:
            self._values.api_message = "API error, no data returned"
            _LOGGER.warning(
                "%s: API did not return any data for team '%s'", self._sensor_name, self._team_id
            )
            return False

        return True


    #
    #  finalize_sensor_values()
    #    Do final adjustments to sensor values
    #
    def finalize_sensor_values(self, provider_response) -> bool:

        # If NOT_FOUND, and team_id is an integer, try to get the abbr from the team_list lookup
        if (self._values.state == "NOT_FOUND" and is_integer(self._team_id)):
            teams = provider_response.get("lookups", {}).get("team_list", [])
            if teams:
                team_abbr = next(
                    (team["abbreviation"] for team in teams if team["id"] == self._team_id),
                    None,
                )
            else:
                team_abbr = None

            self._values.team_id = self._team_id
            if team_abbr:
                self._values.team_abbr = team_abbr


        # "cache_flag" key only exists in cached data, so update the API message if appropriate
        if provider_response.get("cache_flag", False):
            if self._values.api_message:
                self._values.api_message = "Cached data: " + self._values.api_message
            else:
                self._values.api_message = "Cached data"

        return True




    @abstractmethod
    #
    #  setup()
    #
    def setup(self,
        sensor_name, sport_path, league_path, league_id, team_id
    ) -> bool:
        pass


    @abstractmethod
    #
    #  async_parse_response()
    #
    async def async_parse_response(
        self,
        provider_response, 
        lang
    ) -> TeamTrackerValues:

        pass                                               # pylint: disable=unnecessary-pass
