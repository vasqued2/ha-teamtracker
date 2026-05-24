""" TeamTracker Data Coordinator """
import locale
import logging

from async_timeout import timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_LANGUAGE,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    DEFAULT_TIMEOUT,
)
from .models import TeamTrackerValues
from .parser_factory import get_parser
from .provider_base import BaseSportProvider
from .provider_factory import get_provider
from .utils import is_integer

_LOGGER = logging.getLogger(__name__)


class TeamTrackerCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TeamTracker data."""

    def __init__(self, hass, config, entry: ConfigEntry=None):
        """Initialize."""
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
        self.parser.setup(self.name, self.sport_path, self.league_path, self.league_id, self.team_id)

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

        self.parser.setup(self.name, self.sport_path, self.league_path, self.league_id, self.team_id)


    #
    #  DataUpdateCoordinator Call Tree
    #
    #  _async_update_data() - Top-level method called from HA to update sensor, controls refresh rate
    #    async_update_sport_data() - Provider method to return response from data provider (cached or real-time)
    #    async_update_values() - Returns sensor values based on response returned by data provider
    #
    async def _async_update_data(self):
        """Top-level method called from HA to update sensor, controls refresh rate."""
        async with timeout(DEFAULT_TIMEOUT):
            try:
                response = await self.provider.async_update_sport_data()
                values = await self.async_update_values(response)

                # update the interval based on flag
                if values.private_fast_refresh:
                    refresh_rate = self.provider.RAPID_REFRESH_RATE
                else:
                    refresh_rate = self.provider.DEFAULT_REFRESH_RATE

                if self.update_interval != refresh_rate:
                    self.update_interval = refresh_rate
                    _LOGGER.debug(
                        "%s: Updating to refresh rate (%s)", self.name, self.update_interval
                    )
            except Exception as error:
                _LOGGER.warning("%s: Error updating data: %s", self.name, error)
                _LOGGER.warning("%s: Error type: %s", self.name, type(error).__name__)
                _LOGGER.warning("%s: Additional information: %s", self.name, str(error))
                raise UpdateFailed(error) from error
            return values


    #
    #  async_update_values()
    #
    async def async_update_values(self, provider_response) -> TeamTrackerValues:
        """Updates sensor values using data returned by API or in cache"""

        data = provider_response["data"]
        team_id = self.team_id.upper()
        lang = self.get_lang()

        # When league_path is "all", parser needs league_map{} to do manual lookup
        league_map = {}
        if (self.league_path) == "all":
            cache_key = f"{self.sport_path}:{self.league_path}:{self.team_id}"
            team_cache = BaseSportProvider.all_team_cache.get(cache_key)
            if team_cache:
                league_map = team_cache.get("league_map", {})

        # Parse the data returned from the API and get the values
        values = await self.parser.async_parse_response(
            provider_response,
            league_map,
            lang,
        )

        if data is None:
            return values

        # "cache_flag" key only exists in cached data, so update the API message if appropriate
        if provider_response.get("cache_flag", False):
            if values.api_message:
                values.api_message = "Cached data: " + values.api_message
            else:
                values.api_message = "Cached data"

        # If NOT_FOUND, try to get abbr w/ another API to make message easier to read
        if (values.state == "NOT_FOUND" and 
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

            values.team_id = team_id
            if team_abbr:
                values.team_abbr = team_abbr

        return values

