from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DEFAULT_DATA_FORMAT = "espn_json"

class BaseSportProvider(ABC):
    """Base class for all sport data providers."""

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
