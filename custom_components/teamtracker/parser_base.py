""" Base class for all parsers """
from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import TYPE_CHECKING

from .const import DEFAULT_LOGO, DOMAIN, OVERRIDE_DICT
from .models import TeamTrackerValues
from .utils import is_integer

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class BaseSportParser(ABC):
    """Base class for all sport data providers."""

    def __init__(self, coordinator: TeamTrackerCoordinator) -> None:
        # Define the attributes that must be available on all providers
        self._values: TeamTrackerValues = TeamTrackerValues()
        self._coordinator = coordinator
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

        rc = self.override_sensor_values()

        return rc


    #
    #  override_sensor_values()
    #    Apply any overrides from the override files
    #
    def override_sensor_values(self) -> bool:

        class Default(dict):
            def __missing__(self, key):
                return f"{{{key}}}"

        def apply_override(override):
            if override is None:
                return None
            if not isinstance(override, str):
                return override
            m = Default(**self._values.to_dict_all_attr())
            return override.format_map(m)

        if self._coordinator is None:
            return True

        override_dict = self._coordinator.hass.data[DOMAIN].get(OVERRIDE_DICT, {})
        overrides = override_dict.get(str(self._values.sport_path).lower(), {}).get(str(self._values.league_path).lower(), None)
        if overrides is None:
            return True

        self._values.league_name = apply_override(overrides.get("league_name", self._values.league_name))
        self._values.league_logo = apply_override(overrides.get("league_logo", self._values.league_logo))
        self._values.event_url = apply_override(overrides.get("event_url", self._values.event_url))

        team_id = self._values.team_id
        team_overrides = overrides.get("teams", {}).get(team_id, None)
        if team_overrides is not None:
            self._values.team_abbr = apply_override(team_overrides.get("abbr", self._values.team_abbr))
            self._values.team_long_name = apply_override(team_overrides.get("long_name", self._values.team_long_name))
            self._values.team_name = apply_override(team_overrides.get("name", self._values.team_name))
            self._values.team_logo = apply_override(team_overrides.get("logo", self._values.team_logo))
            self._values.team_url = apply_override(team_overrides.get("url", self._values.team_url))
            self._values.team_colors = apply_override(team_overrides.get("colors", self._values.team_colors))

        opponent_id = self._values.opponent_id
        opponent_overrides = overrides.get("teams", {}).get(opponent_id, None)
        if opponent_overrides is not None:
            self._values.opponent_abbr = apply_override(opponent_overrides.get("abbr", self._values.opponent_abbr))
            self._values.opponent_long_name = apply_override(opponent_overrides.get("long_name", self._values.opponent_long_name))
            self._values.opponent_name = apply_override(opponent_overrides.get("name", self._values.opponent_name))
            self._values.opponent_logo = apply_override(opponent_overrides.get("logo", self._values.opponent_logo))
            self._values.opponent_url = apply_override(opponent_overrides.get("url", self._values.opponent_url))
            self._values.opponent_colors = apply_override(opponent_overrides.get("colors", self._values.opponent_colors))

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
    #  parse_response()
    #
    def parse_response(
        self,
        provider_response, 
        lang
    ) -> TeamTrackerValues:

        pass                                               # pylint: disable=unnecessary-pass
