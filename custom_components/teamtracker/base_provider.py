from abc import ABC, abstractmethod
from datetime import timedelta

from homeassistant.core import HomeAssistant

class BaseSportProvider(ABC):
    """Base class for all sport data providers."""

    def __init__(self) -> None:
        # Define the attributes that must be available on all providers
        self.DATA_PROVIDER: str = "default"
        self.ATTRIBUTION: str = ""
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=5)

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
    async def async_fetch_game_data(
        self,
        hass,
        league_id: str,
        sensor_name: str,
        lang: str,
    ) -> dict:
        """Fetch and return sport data in the standard format."""
        pass                                               # pylint: disable=unnecessary-pass
