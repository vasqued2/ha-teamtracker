""" Base class for all data providers """
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from .const import DOMAIN, OVERRIDE_DICT
from .utils import load_file_overrides

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

_LOGGER = logging.getLogger(__name__)


class BaseSportProvider(ABC):
    """Base class for all sport data providers."""

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        # Define the attributes that must be available on all providers
        self.DATA_PROVIDER: str = "base"
        self.ATTRIBUTION: str = ""
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=5)
        self.data_format = "base"
        self._coordinator = coordinator
        if self._coordinator:
            self.data_cache = self._coordinator.hass.data.setdefault(DOMAIN, {}).setdefault("data_cache", {})
        else: # coordinator is None when called from Config Flow
            self.data_cache = {}
        self._USER_AGENT = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_6) AppleWebKit/605.1.15 (KHTML, like "
            "Gecko) Version/15.0 Safari/605.1.15"
        )


    #
    #  async_update_sport_data()
    #
    async def async_update_sport_data(self) -> dict:
        """Determines to use cached data or API call (if exprired)"""

        #
        #  Call API to get refreshed response and cache it
        #
        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        response = await self.async_get_scoreboard_data(self._coordinator.hass, self._coordinator.get_lang())

        return response


    #
    #  _get_from_cache()
    #    Return cached response if not expired
    #
    def _get_from_cache(self, 
        cache_name: str, 
        key: str,
        duration: timedelta
        ) -> dict | None:
        """Return cache key"""

        response = self.data_cache.get(cache_name, {}).get(key, {}).get("response", None)
        if response:
            timestamp = response.get("timestamp", None)
            if isinstance(timestamp, str):
                expiration = datetime.fromisoformat(timestamp) + duration
                now = datetime.now(timezone.utc)

                if now < expiration:
                    response.update({"cache_flag": True}) # Add key to indicate cache was used
                    return response
            else:
                _LOGGER.warning(
                    "_get_from_cache(): Cache entry does not have string timestamp for key '%s' timestamp = '%s'",
                    key,
                    timestamp
                )

        return None


    #
    #  _save_to_cache()
    #    Save response to cache
    #
    def _save_to_cache(self, 
        cache_name: str, 
        key: str,
        response: dict | None
        ) -> None:
        """Return cache key"""

        if response:
            live_data = response.get("live_data", False)
            data = response.get("data", None)
            if not live_data and data is not None:
                self.data_cache.setdefault(cache_name, {}).setdefault(key, {})["response"] = response


    #
    #  _get_cache_key()
    #
    @abstractmethod
    def _get_cache_key(self) -> str:
        """Return cache key"""
        pass                                               # pylint: disable=unnecessary-pass


    #
    #  _load_override_dict()
    #
    async def _async_load_override_dict(
        self,
        hass:HomeAssistant) -> bool:

        # Initialize DOMAIN in hass.data if it doesn't exist
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        # Load the OVERRIDE_DICT if it doesn't exist
        if OVERRIDE_DICT not in hass.data[DOMAIN]:
            hass.data[DOMAIN][OVERRIDE_DICT] = None
            override_dict = await hass.async_add_executor_job(load_file_overrides, hass)
            if OVERRIDE_DICT not in hass.data[DOMAIN] or hass.data[DOMAIN][OVERRIDE_DICT] is None:
                hass.data[DOMAIN][OVERRIDE_DICT] = override_dict

        return True


    #
    #  async_get_team_data()
    #    Return data from cache or call fetch if needed
    #
    async def async_get_team_data(
        self,
        hass: HomeAssistant, 
        sport_path: str="",
        league_path: str="",
        sensor_name: str="ConfigFlow-teams",
    ) -> dict:
        """Return data from cache and call fetch if needed."""
        CACHE_NAME = "team_data"

        #  If cached, return response
        key = self._get_cache_key()
        duration = timedelta(hours=24)
        response = self._get_from_cache(CACHE_NAME, key, duration)
        if response:
            response.update({"cache_flag": True}) # Add key to indicate cache was used
            return response

        # Fetch data and save to cache
        response = await self._async_fetch_team_data(hass, sport_path, league_path, sensor_name)
        self._save_to_cache(CACHE_NAME, key, response)

        return response


    async def _async_fetch_team_data(
        self,
        hass: HomeAssistant, 
        sport_path: str,
        league_path: str,
        sensor_name: str,
    ) -> dict:
        """Fetch and return team data in the standard format."""
        return {"data": None, "url": None, "timestamp": None}


    #
    #  async_get_scoreboard_data()
    #    Return data from cache or call fetch if needed
    #
    async def async_get_scoreboard_data(
        self,
        hass,
        lang: str,
    ) -> dict:
        """Return data from cache and call fetch if needed."""
        CACHE_NAME = "scoreboard_data"

        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        #  If cached, return response
        key = self._get_cache_key()
        duration = self._coordinator.update_interval
        response = self._get_from_cache(CACHE_NAME, key, duration)
        if response:
            response.update({"cache_flag": True}) # Add key to indicate cache was used
            return response

        # Fetch data and save to cache
        response = await self._async_fetch_scoreboard_data(hass, lang)
        if not response.get("live_flag", False):
            self._save_to_cache(CACHE_NAME, key, response)

        return response


    async def _async_fetch_scoreboard_data(
        self,
        hass,
        lang: str,
    ) -> dict:
        """Fetch and return sport data in the standard format."""

        return {"data": None, "url": None, "timestamp": None}


    async def async_get_team_conference_id(
        self,
        hass: HomeAssistant, 
        sport_path: str, 
        league_path: str, 
        team_id: str
    ) -> str:
        """Fetch conference/group ID for a single team from the ESPN team detail API."""
        return ""
