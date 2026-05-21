""" Base class for all data providers """
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, ClassVar

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DEFAULT_DATA_FORMAT = "espn_json"

class BaseSportProvider(ABC):
    """Base class for all sport data providers."""

    # Stores API data for sharing across sensors
    #  key = "{sport_path}:{league_path}:{conference_id}:{lang}"+":{team_id}" if league_path "all"
    data_cache: ClassVar[dict] = {}  # {key: {response: {data, url, timestamp, cache_flag}}}

    # Stores team information when league_path is all
    #  key = "{sport}:{league}:{team_id}"
    all_team_cache: ClassVar[dict] = {}  # {key: {next_game_date, league_map, expires}}


    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        # Define the attributes that must be available on all providers
        self.DATA_PROVIDER: str = "default"
        self.ATTRIBUTION: str = ""
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=5)
        self.data_format = DEFAULT_DATA_FORMAT
        self._coordinator = coordinator
        self._USER_AGENT = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_6) AppleWebKit/605.1.15 (KHTML, like "
            "Gecko) Version/15.0 Safari/605.1.15"
        )


    #
    #  async_update_sport_data()
    #
    async def async_update_sport_data(self) -> dict:
        """Determines to use cached data or API call (if exprired)"""

        if not self._coordinator:
                        return {"data": None, "url": None, "timestamp": None}
                                #
        #  Return cached response if not expired
        #
        key = self._get_cache_key()
        response = BaseSportProvider.data_cache.get(key, {}).get("response", None)
        if response:
            expiration = datetime.fromisoformat(response["timestamp"]) + self._coordinator.update_interval
            now = datetime.now(timezone.utc)

            if now < expiration:
                response.update({"cache_flag": True}) # Add key to indicate cache was used
                return response

        #
        #  Call API to get refreshed response and cache it
        #
        response = await self.async_fetch_scoreboard_data(self._coordinator.hass, self._coordinator.get_lang())
        if response["data"] is not None:
            BaseSportProvider.data_cache.update({key: {"response": response}})

        return response


    #
    #  _get_cache_key()
    #
    @abstractmethod
    def _get_cache_key(self) -> str:
        """Return cache key"""
        pass                                               # pylint: disable=unnecessary-pass


    @abstractmethod
    async def async_fetch_team_data(
        self,
        hass: HomeAssistant, 
        sport_path: str="",
        league_path: str=""
    ) -> dict:
        """Fetch and return team data in the standard format."""
        pass                                               # pylint: disable=unnecessary-pass

    @abstractmethod
    async def async_fetch_scoreboard_data(
        self,
        hass,
        lang: str,
    ) -> dict:
        """Fetch and return sport data in the standard format."""
        pass                                               # pylint: disable=unnecessary-pass

    async def async_fetch_team_conference_id(
        self,
        hass: HomeAssistant, 
        sport_path: str, 
        league_path: str, 
        team_id: str
    ) -> str:
        """Fetch conference/group ID for a single team from the ESPN team detail API."""
        return ""
