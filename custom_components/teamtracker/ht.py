from .base_provider import BaseSportProvider
from typing import Any, TypedDict
from datetime import timedelta

from homeassistant.core import HomeAssistant

class HockeyTechLeague(TypedDict):
    public_key: str
    client_code: str
    league_name: str
    league_logo: str | None

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
        self.DATA_PROVIDER: str = "hockeytech"
        self.ATTRIBUTION: str = "Powered by HockeyTech.com"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=5)
        self.leagues: dict[str, Any] = HOCKEYTECH_LEAGUES

    async def async_fetch_team_data(
        self,
        hass: HomeAssistant, 
        league_id: str
    ) -> dict:
        # Perform your specific API calls here
        return {"source": "espn", "data": {}, "url": "url"}

    async def async_fetch_game_data(
        self,
        hass,
        league_id: str,
        sensor_name: str,
        lang: str,
    ) -> dict:
        # Perform your specific API calls here
        return {"source": "espn", "data": {}, "url": "url"}