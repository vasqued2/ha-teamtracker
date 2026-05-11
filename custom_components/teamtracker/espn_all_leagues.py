from __future__ import annotations

from homeassistant.core import HomeAssistant
from typing import TYPE_CHECKING

from .espn import EspnProvider

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_ESPN_ALL_LEAGUES = "espn-all_leagues"


class EspnAllLeaguesProvider(EspnProvider):
    """Provider for ESPN data."""

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_ESPN_ALL_LEAGUES


    #
    # Return an empty list of team dictionaries since no way to get teams w/o a league constraint
    #

    async def async_fetch_team_data(self, hass: HomeAssistant, sport_path: str="", league_path: str="") -> dict:
        """There is no API to get all teams for a sport w/o specifying a league so return an empty list."""

        return {"data": [], "url": ""}




    async def async_fetch_scoreboard_data(
        self,
        hass,
        lang: str,
    ) -> dict:
        # Perform your specific API calls here
        return {"source": "espn", "data": {}, "url": "url"}