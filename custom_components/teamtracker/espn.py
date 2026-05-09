from .base_provider import BaseSportProvider
from typing import Any, TypedDict
from datetime import timedelta

from homeassistant.core import HomeAssistant

from .const import (
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
)

from .utils import async_call_espn_api

# Sports
AUSTRALIAN_FOOTBALL = "australian-football"
BASEBALL = "baseball"
BASKETBALL = "basketball"
CRICKET = "cricket"
FOOTBALL = "football"
GOLF = "golf"
HOCKEY = "hockey"
MMA = "mma"
RACING = "racing"
RUGBY = "rugby"
SOCCER = "soccer"
TENNIS = "tennis"
VOLLEYBALL = "volleyball"

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

        self.LEAGUE_MAP = {
            "AFL": {
                CONF_SPORT_PATH: AUSTRALIAN_FOOTBALL,
                CONF_LEAGUE_PATH: "afl",
            },
            "MLB": {
                CONF_SPORT_PATH: BASEBALL,
                CONF_LEAGUE_PATH: "mlb",
            },
            "NBA": {
                CONF_SPORT_PATH: BASKETBALL,
                CONF_LEAGUE_PATH: "nba",
            },
            "WNBA": {
                CONF_SPORT_PATH: BASKETBALL,
                CONF_LEAGUE_PATH: "wnba",
            },
            "NCAAM": {
                CONF_SPORT_PATH: BASKETBALL,
                CONF_LEAGUE_PATH: "mens-college-basketball",
            },
            "NCAAW": {
                CONF_SPORT_PATH: BASKETBALL,
                CONF_LEAGUE_PATH: "womens-college-basketball",
            },
            "NCAAF": {
                CONF_SPORT_PATH: FOOTBALL,
                CONF_LEAGUE_PATH: "college-football",
            },
            "NFL": {
                CONF_SPORT_PATH: FOOTBALL,
                CONF_LEAGUE_PATH: "nfl",
            },
            "XFL": {
                CONF_SPORT_PATH: FOOTBALL,
                CONF_LEAGUE_PATH: "xfl",
            },
            "PGA": {
                CONF_SPORT_PATH: GOLF,
                CONF_LEAGUE_PATH: "pga",
            },
            "NHL": {
                CONF_SPORT_PATH: HOCKEY,
                CONF_LEAGUE_PATH: "nhl",
            },
            "PWHL": {
                CONF_SPORT_PATH: HOCKEY,
                CONF_LEAGUE_PATH: "pwhl",
            },
            "UFC": {
                CONF_SPORT_PATH: MMA,
                CONF_LEAGUE_PATH: "ufc",
            },
            "F1": {
                CONF_SPORT_PATH: RACING,
                CONF_LEAGUE_PATH: "f1",
            },
            "IRL": {
                CONF_SPORT_PATH: RACING,
                CONF_LEAGUE_PATH: "irl",
            },
            "NASCAR": {
                CONF_SPORT_PATH: RACING,
                CONF_LEAGUE_PATH: "nascar-premier",
            },
            "BUND": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "ger.1",
            },
            "CL": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "uefa.champions",
            },
            "CLA": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "conmebol.libertadores",
            },
            "EPL": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "eng.1",
            },
            "LIGA": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "esp.1",
            },
            "LIG1": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "fra.1",
            },
            "MLS": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "usa.1",
            },
            "NWSL": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "usa.nwsl",
            },
            "SERA": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "ita.1",
            },
            "WC": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "fifa.world",
            },
            "WWC": {
                CONF_SPORT_PATH: SOCCER,
                CONF_LEAGUE_PATH: "fifa.wwc",
            },
            "ATP": {
                CONF_SPORT_PATH: TENNIS,
                CONF_LEAGUE_PATH: "atp",
            },
            "WTA": {
                CONF_SPORT_PATH: TENNIS,
                CONF_LEAGUE_PATH: "wta",
            },
            "NCAAVB": {
                CONF_SPORT_PATH: VOLLEYBALL,
                CONF_LEAGUE_PATH: "mens-college-volleyball",
            },
            "NCAAVBW": {
                CONF_SPORT_PATH: VOLLEYBALL,
                CONF_LEAGUE_PATH: "womens-college-volleyball",
            },
        }


    #
    # Return a list of team dictionaries
    #  [{
    #   "id": team_id,
    #   "displayName": Long Team Name
    #   "location": City, State, Country of team
    #    "conference_id": Conference for the team (NCAA Only)
    #  }]
    #

    async def async_fetch_team_data(self, hass: HomeAssistant, league_id: str, sport_path: str="", league_path: str="") -> dict:
        """Fetch teams from any API for a given league."""
        if league_id not in self.LEAGUE_MAP:
            sport = sport_path
            league = league_path
        else:
            paths = self.LEAGUE_MAP[league_id]
            sport = paths[CONF_SPORT_PATH]
            league = paths[CONF_LEAGUE_PATH]
        url = (
            f"https://site.api.espn.com/apis/site/v2/sports"
            f"/{sport}/{league}/teams"
        )
        url_parms = {"limit": 1000}
        response = await async_call_espn_api(hass, url, url_parms, "ConfigFlow-teams", league)
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