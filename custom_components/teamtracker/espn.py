from datetime import timedelta

from homeassistant.core import HomeAssistant

from .base_provider import BaseSportProvider
from .utils import async_call_espn_api

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
DATA_PROVIDER_ESPN = "espn"

class EspnProvider(BaseSportProvider):
    """Provider for ESPN data."""

    def __init__(self) -> None:
        super().__init__()
        self.DATA_PROVIDER: str = DATA_PROVIDER_ESPN
        self.ATTRIBUTION: str = "Data provided by ESPN"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=5)



    #
    # Return a list of team dictionaries
    #  [{
    #   "id": team_id,
    #   "displayName": Long Team Name
    #   "location": City, State, Country of team
    #    "conference_id": Conference for the team (NCAA Only)
    #  }]
    #

    async def async_fetch_team_data(self, hass: HomeAssistant, sport_path: str="", league_path: str="") -> dict:
        """Fetch teams from any API for a given league."""

        url = (
            f"{ESPN_BASE_URL}/{sport_path}/{league_path}/teams"
        )
        url_parms = {"limit": 1000}
        response = await async_call_espn_api(hass, url, url_parms, "ConfigFlow-teams", league_path)
        data = response["data"]
        url = response["url"]
        if data:
            raw = (
                data.get("sports", [{}])[0]
                .get("leagues", [{}])[0]
                .get("teams", [])
            )
        else:
            raw = []

        # Build the teams data
        teams = []
        for entry in raw:
            t = entry.get("team", {})
            teams.append({
                "id":            t.get("id", ""),
                "abbreviation":  t.get("abbreviation", ""),
                "displayName":   t.get("displayName", t.get("name", "")),
                "location":      t.get("location", ""),
                "conference_id": (t.get("groups") or {}).get("id", ""),
            })
        return {"data": teams, "url": url}




    async def async_fetch_game_data(
        self,
        hass,
        league_id: str,
        sensor_name: str,
        lang: str,
    ) -> dict:
        # Perform your specific API calls here
        return {"source": "espn", "data": {}, "url": "url"}