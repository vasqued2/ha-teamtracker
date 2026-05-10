from homeassistant.core import HomeAssistant

from .espn import EspnProvider

DATA_PROVIDER_ESPN_ALL_LEAGUES = "espn-all_leagues"


class EspnAllLeaguesProvider(EspnProvider):
    """Provider for ESPN data."""

    def __init__(self) -> None:
        super().__init__()
        self.DATA_PROVIDER: str = DATA_PROVIDER_ESPN_ALL_LEAGUES


    #
    # Return an empty list of team dictionaries since no way to get teams w/o a league constraint
    #

    async def async_fetch_team_data(self, hass: HomeAssistant, sport_path: str="", league_path: str="") -> dict:
        """There is no API to get all teams for a sport w/o specifying a league so return an empty list."""

        return {"data": [], "url": ""}




    async def async_fetch_game_data(
        self,
        hass,
        league_id: str,
        sensor_name: str,
        lang: str,
    ) -> dict:
        # Perform your specific API calls here
        return {"source": "espn", "data": {}, "url": "url"}