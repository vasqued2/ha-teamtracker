from .base_provider import BaseSportProvider
from typing import Any, TypedDict
from datetime import timedelta

from homeassistant.core import HomeAssistant

class ESPNLeague(TypedDict):
    league_name: str
#    league_logo: str | None
#    client_code: str
#    public_key: str

ESPN_LEAGUES: dict[str, ESPNLeague]  = {
    "AFL": {
        "league_name": "Australian Football League",
    },
    "MLB": {
        "league_name": "Major League Baseball",
    },
    "NBA": {
        "league_name": "National Basketball Association",
    },
    "WNBA": {
        "league_name": "Women's National Basketball Association",
    },
    "NCAAM": {
        "league_name": "Men's NCAA Basketball",
    },
    "NCAAW": {
        "league_name": "Women's NCAA Basketball",
    },
    "NCAAF": {
        "league_name": "NCAA Football",
    },
    "NFL": {
        "league_name": "National Football League",
    },
    "XFL": {
        "league_name": "X Football League",
    },
    "PGA": {
        "league_name": "Professional Golfers Association",
    },
    "NHL": {
        "league_name": "National Hockey League",
    },
    "PWHL": {
        "league_name": "Professional Women's Hockey League",
    },
    "UFC": {
        "league_name": "Ultimate Fighting Championship",
    },
    "F1": {
        "league_name": "F1 Racing",
    },
    "IRL": {
        "league_name": "Indy Racing League",
    },
    "NASCAR": {
        "league_name": "NASCAR",
    },
    "BUND": {
        "league_name": "Bundesliga",
    },
    "CL": {
        "league_name": "Champions League",
    },
    "CLA": {
        "league_name": "Conmebol Libertadores",
    },
    "EPL": {
        "league_name": "English Premiere League",
    },
    "LIGA": {
        "league_name": "LaLiga",
    },
    "LIG1": {
        "league_name": "Ligue 1",
    },
    "MLS": {
        "league_name": "Major League Soccer",
    },
    "NWSL": {
        "league_name": "Natioal Women's Soccer League",
    },
    "SERA": {
        "league_name": "Serie A",
    },
    "WC": {
        "league_name": "World Cup",
    },
    "WWC": {
        "league_name": "Women's World Cup",
    },
    "ATP": {
        "league_name": "Association of Tennis Professionals",
    },
    "WTA": {
        "league_name": "Women's Tennis Association",
    },
    "NCAAVB": {
        "league_name": "Men's NCAA Volleyball",
    },
    "NCAAVBW": {
        "league_name": "Women's NCAA Volleyball",
    },
}

class EspnProvider(BaseSportProvider):
    """Provider for ESPN data."""

    def __init__(self) -> None:
        super().__init__()
        self.DATA_PROVIDER: str = "espn"
        self.ATTRIBUTION: str = "Data provided by ESPN"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=5)
        self.leagues: dict[str, Any] = ESPN_LEAGUES

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