""" TeamTracker Data Coordinator """
from datetime import datetime, timezone
import locale
import logging

import arrow
from async_timeout import timeout
from typing import ClassVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .clear_values import async_clear_values

from .const import (
    CONF_API_LANGUAGE,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    DEFAULT_LOGO,
    DEFAULT_TIMEOUT,
)
from .parser_factory import get_parser
from .provider_factory import get_provider

from .utils import is_integer

_LOGGER = logging.getLogger(__name__)


class TeamTrackerCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TeamTracker data."""

# Stores API data for sharing across sensors
#  key = "{sport_path}:{league_path}:{conference_id}:{lang}"+":{team_id}" if league_path "all"
    data_cache: ClassVar[dict] = {}  # {key: {cache_data, cache_url, cache_time}}

# Stores team information when league_path is all
#  key = "{sport}:{league}:{team_id}"
    all_team_cache: ClassVar[dict] = {}  # {key: {next_game_date, league_map, expires}}

    def __init__(self, hass, config, entry: ConfigEntry=None):
        """Initialize."""
        self.api_url = ""

        self.name = config[CONF_NAME]
        self.team_id = config[CONF_TEAM_ID]
        self.league_id = config[CONF_LEAGUE_ID]
        self.league_path = config[CONF_LEAGUE_PATH]
        self.sport_path = config[CONF_SPORT_PATH]
        self.conference_id = ""
        if CONF_CONFERENCE_ID in config.keys():
            if len(config[CONF_CONFERENCE_ID]) > 0:
                self.conference_id = config[CONF_CONFERENCE_ID]

        self.provider = get_provider(self.sport_path, self.league_path, self.team_id, self)
        self.parser = get_parser(self.provider.data_format)
        self.parser.setup(self.name, self.sport_path, self.league_id, self.team_id)

        self.update_interval = self.provider.DEFAULT_REFRESH_RATE

        self.config = config
        self.hass = hass
        self.entry = entry #None if setup from YAML

        super().__init__(hass, _LOGGER, name=self.name, update_interval=self.provider.DEFAULT_REFRESH_RATE)
        _LOGGER.debug(
            "%s: Using default refresh rate (%s)", self.name, self.update_interval
        )


    #
    #  Return the language to use for the API
    #
    def get_lang(self):
        """Return language to use for API."""

        try:
            lang = self.hass.config.language
        except:
            lang, _ = locale.getlocale()
            lang = lang or "en_US"

        # Override language if is set in the configuration or options

        if CONF_API_LANGUAGE in self.config.keys():
            lang = self.config[CONF_API_LANGUAGE].lower()
        if self.entry and self.entry.options and CONF_API_LANGUAGE in self.entry.options and len(self.entry.options[CONF_API_LANGUAGE])>=2:
                lang = self.entry.options[CONF_API_LANGUAGE].lower()

        return lang


    #
    #  Set team info from service call
    #
    def update_team_info(self, sport_path, league_path, team_id, conference_id=""):
        """update team information when call_api service is called."""

        self.sport_path = sport_path
        self.league_path = league_path
        self.league_id = "XXX"
        self.team_id = team_id
        self.conference_id = conference_id

        lang = self.get_lang()
        key = sport_path + ":" + league_path + ":" + conference_id + ":" + lang
        if league_path == "all" and is_integer(self.team_id):
            key += ":" + team_id

        if key in TeamTrackerCoordinator.data_cache:
            TeamTrackerCoordinator.data_cache.pop(key, None)
            
        self.parser.setup(self.name, self.sport_path, self.league_id, self.team_id)


    #
    #  DataUpdateCoordinator Call Tree
    #
    #  _async_update_data() - Top-level method called from HA to update sensor, controls refresh rate
    #    async_update_sport_data() - Determines to use cached data or API call (if exprired)
    #      async_call_sport_apis() - Calls appropriate set of APIs based on sport and league
    #        async_fetch_scoreboard_data() - Gets data from ESPN APIs for specified league
    #      async_update_values() - Updates sensor values using data returned by API or in cache
    #        async_process_event() - Parses ESPN event structure and populates values for sensor
    #
    async def _async_update_data(self):
        """Top-level method called from HA to update sensor, controls refresh rate."""
        async with timeout(DEFAULT_TIMEOUT):
            try:
                data = await self.async_update_sport_data()

                # update the interval based on flag
                if data["private_fast_refresh"]:
                    if self.update_interval != self.provider.RAPID_REFRESH_RATE:
                        self.update_interval = self.provider.RAPID_REFRESH_RATE
                        _LOGGER.debug(
                            "%s: Switching to rapid refresh rate (%s)", self.name, self.update_interval
                        )
                else:
                    if self.update_interval != self.provider.DEFAULT_REFRESH_RATE:
                        self.update_interval = self.provider.DEFAULT_REFRESH_RATE
                        _LOGGER.debug(
                            "%s: Switching to default refresh rate (%s)", self.name, self.update_interval
                        )
            except Exception as error:
                _LOGGER.debug("%s: Error updating data: %s", self.name, error)
                _LOGGER.debug("%s: Error type: %s", self.name, type(error).__name__)
                _LOGGER.debug("%s: Additional information: %s", self.name, str(error))
                raise UpdateFailed(error) from error
            return data

#
#  async_update_sport_data()
#
    async def async_update_sport_data(self) -> dict:
        """Determines to use cached data or API call (if exprired)"""

        sport_path = self.sport_path
        league_path = self.league_path
        conference_id = self.conference_id

        lang = self.get_lang()

        # For "all" leagues, include team_id in cache key since each team
        # uses different narrow date windows for the scoreboard call.
        key = sport_path + ":" + league_path + ":" + conference_id + ":" + lang
        if league_path == "all" and is_integer(self.team_id):
            key += ":" + self.team_id

        #
        #  Use cache if not expired
        #
        dc = TeamTrackerCoordinator.data_cache.get(key, None)
        if dc:
            cache_time = dc.get("cache_time", None)

            expiration = (
                datetime.fromisoformat(cache_time) + self.update_interval
            )
            now = datetime.now(timezone.utc)

            if now < expiration:
                data = dc.get("cache_data", None)
                self.api_url = dc.get("cache_url", None)

                values = await self.async_update_values(data)

                if values["api_message"]:
                    values["api_message"] = "Cached data: " + values["api_message"]
                else:
                    values["api_message"] = "Cached data"

                return values

        data = await self.async_call_sport_apis()
        values = await self.async_update_values(data)

        if data is not None:
            TeamTrackerCoordinator.data_cache[key] = {
                "cache_data": data,
                "cache_url": self.api_url,
                "cache_time": values["last_update"]
            }

        return values


    #
    #  async_call_sport_apis()
    #    This is the API dispatcher, calls to new non-ESPN API's should be added here based on league_path.
    #      Response data should be formatted as an ESPN event.
    #
    async def async_call_sport_apis(self) -> dict:
        """Calls appropriate set of APIs based on sport and league."""

        lang = self.get_lang()
        response = await self.provider.async_fetch_scoreboard_data(self.hass, lang)

        self.api_url = response["url"]
        return response["data"]


    #
    #  async_update_values()
    #
    async def async_update_values(self, data) -> dict:
        """Updates sensor values using data returned by API or in cache"""

        sensor_name = self.name
        league_id = self.league_id.upper()
        team_id = self.team_id.upper()
        lang = self.get_lang()

        # Populate base values that do not need API data
        values = {}
        values = await async_clear_values()
        if self.sport_path.lower() == "hockeytech":
            values["sport"] = "hockey"
        else:
            values["sport"] = self.sport_path
        values["sport_path"] = self.sport_path
        values["league"] = league_id
        values["league_path"] = self.league_path
        values["league_logo"] = DEFAULT_LOGO
        values["team_abbr"] = team_id
        values["state"] = "NOT_FOUND"
        values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
        values["private_fast_refresh"] = False
        values["api_url"] = self.api_url

        # If there was an error (i.e. 404) w/ the API call...
        if data is None:
            values["api_message"] = "API error, no data returned"
            _LOGGER.warning(
                "%s: API did not return any data for team '%s'", sensor_name, team_id
            )
            return values

        # When league_path is "all", parser needs league_map{} to do manual lookup
        league_map = {}
        if (self.league_path) == "all":
            cache_key = f"{self.sport_path}:{self.league_path}:{self.team_id}"
            team_cache = TeamTrackerCoordinator.all_team_cache.get(cache_key)
            if team_cache:
                league_map = team_cache.get("league_map", {})

        values = await self.parser.async_process_event(
            values,
            data,
            league_map,
            lang,
        )

        # If NOT_FOUND, try to get abbr w/ another API to make message easier to read
        if (values["state"] == "NOT_FOUND" and 
            is_integer(team_id)
        ):
            response = await self.provider.async_fetch_team_data(self.hass, self.sport_path, self.league_path)
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
