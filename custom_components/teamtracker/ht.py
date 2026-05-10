from .base_provider import BaseSportProvider
from typing import TypedDict
from datetime import timedelta
import locale
import logging

from homeassistant.core import HomeAssistant

from .hockeytech import async_call_hockeytech_api

class HockeyTechLeague(TypedDict):
    public_key: str
    client_code: str
    league_name: str
    league_logo: str | None

_LOGGER = logging.getLogger(__name__)

HOCKEYTECH_BASE_URL = "https://lscluster.hockeytech.com/feed/index.php"
DATA_PROVIDER_HOCKEYTECH = "hockeytech"

HOCKEYTECH_LEAGUES: dict[str, HockeyTechLeague]  = {
    "CHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "chl",
        "league_name": "Canadian Hockey League",
        "league_logo": None,
    },
    "OHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "ohl",
        "league_name": "Ontario Hockey League",
        "league_logo": None,
    },
    "WHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "whl",
        "league_name": "Wester Hockey League",
        "league_logo": None,
    },
    "LHJMQ": {
        "public_key": "f1aa699db3d81487",
        "client_code": "lhjmq",
        "league_name": "Quebec Major Junior Hockey League",
        "league_logo": None,
    },
    "AHL": {
        "public_key": "50c2cd9b5e18e390",
        "client_code": "ahl",
        "league_name": "American Hockey League",
        "league_logo": None,
    },
    "ECHL": {
        "public_key": "2c2b89ea7345cae8",
        "client_code": "echl",
        "league_name": "East Coast Hockey League",
        "league_logo": None,
    },
    "PWHL": {
        "public_key": "446521baf8c38984",
        "client_code": "pwhl",
        "league_name": "Professional Womens Hockey League",
        "league_logo": "https://assets.leaguestat.com/pwhl/logos/pwhl.png",
    },
    "USHL": {
        "public_key": "e828f89b243dc43f",
        "client_code": "ushl",
        "league_name": "United States Hockey League",
        "league_logo": None,
    },
    "OJHL": {
        "public_key": "77a0bd73d9d363d3",
        "client_code": "ojhl",
        "league_name": "Ontario Junior Hockey League",
        "league_logo": None,
    },
    "BCHL": {
        "public_key": "ca4e9e599d4dae55",
        "client_code": "bchl",
        "league_name": "British Columbia Hockey League",
        "league_logo": None,
    },
    "SJHL": {
        "public_key": "2fb5c2e84bf3e4a8",
        "client_code": "sjhl",
        "league_name": "Saskatchewan Junior Hockey League",
        "league_logo": None,
    },
    "AJHL": {
        "public_key": "cbe60a1d91c44ade",
        "client_code": "ajhl",
        "league_name": "Alberta Junior Hockey League",
        "league_logo": None,
    },
    "MJHL": {
        "public_key": "f894c324fe5fd8f0",
        "client_code": "mjhl",
        "league_name": "Manitoba Junior Hockey League",
        "league_logo": None,
    },
    "MHL": {
        "public_key": "4a948e7faf5ee58d",
        "client_code": "mhl",
        "league_name": "Maritime Junior Hockey League",
        "league_logo": None,
    },
}


class HockeyTechProvider(BaseSportProvider):
    """Provider for HockeyTech data."""

    def __init__(self) -> None:
        super().__init__()
        self.DATA_PROVIDER: str = DATA_PROVIDER_HOCKEYTECH
        self.ATTRIBUTION: str = "Powered by HockeyTech.com"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=60)


    #
    # Return a list of team dictionaries
    #  [{
    #   "id": team_id,
    #   "displayName": Long Team Name
    #   "location": City, State, Country of team
    #    "conference_id": Conference for the team (NCAA Only)
    #  }]
    #

    async def async_fetch_team_data(self, hass: HomeAssistant, sport_path: str="", league_path: str ="") -> dict:
        """Fetch teams from any API for a given league."""

        sensor_name = "hockeytech_teamsbyseason"
        league_abbr = league_path.upper()
        league_config = HOCKEYTECH_LEAGUES.get(league_abbr)
        if league_config is None:
            _LOGGER.warning(
                "%s: No HockeyTech config for league '%s'", sensor_name, league_abbr
            )
            return {"data": None, "url": None}

        try:
            lang = hass.config.language
        except:
            lang, _ = locale.getlocale()
            lang = lang or "en"

    #
    #   Get the most recent regular season
    #      career = 1, playoffs = 0
    #
        params = {
            "feed": "modulekit",
            "view": "seasons",
            "key": league_config["public_key"],
            "client_code": league_config["client_code"],
        }

        ht_response = await async_call_hockeytech_api(hass, HOCKEYTECH_BASE_URL, params, sensor_name, league_abbr)
        ht_data = ht_response["ht_data"]
        url = ht_response["url"]

        if ht_data:
            seasons = (
                ht_data.get("SiteKit", [{}])
                .get("Seasons", [])
            )
        else:
            seasons = []

        season = {}
        for s in seasons:
            if s["career"] == "1" and s["playoff"] == "0":
                season = s
                break

        season_id = season.get("season_id", 0)

    #
    #   Get the list of teams for the most recent regular season
    #
        params = {
            "feed": "modulekit",
            "view": "teamsbyseason",
            "season_id": season_id,                                         # Hardcode 25/26 PWHL Season
            "key": league_config["public_key"],
            "client_code": league_config["client_code"],
            "lang": lang,
            "fmt": "json",
        }

        ht_response = await async_call_hockeytech_api(hass, HOCKEYTECH_BASE_URL, params, sensor_name, league_abbr)
        ht_data = ht_response["ht_data"]
        url = ht_response["url"]

        if ht_data:
            raw = (
                ht_data.get("SiteKit", [{}])
                .get("Teamsbyseason", [])
            )
        else:
            raw = []

        # Build the teams data
        teams = []
        for t in raw:
            teams.append({
                "id":            t.get("id", ""),
                "abbreviation":  t.get("code", t.get("abbreviation", "")),
                "displayName":   t.get("name", ""),
                "location":      t.get("city", ""),
                "conference_id": "",
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