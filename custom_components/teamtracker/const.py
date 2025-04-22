""" Constants for teamtracker sensor"""
from homeassistant.const import Platform
from datetime import timedelta

# API
URL_HEAD = "http://site.api.espn.com/apis/site/v2/sports/"
URL_TAIL = "/scoreboard"
API_LIMIT = 50
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_6) AppleWebKit/605.1.15 (KHTML, like "
    "Gecko) Version/15.0 Safari/605.1.15"
)

# Config
CONF_API_LANGUAGE = "api_language"
CONF_CONFERENCE_ID = "conference_id"
CONF_LEAGUE_ID = "league_id"
CONF_LEAGUE_PATH = "league_path"
CONF_SPORT_PATH = "sport_path"
CONF_TEAM_ID = "team_id"

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

# Maps
LEAGUE_MAP = {
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

SPORT_ICON_MAP = {
    AUSTRALIAN_FOOTBALL: "mdi:football-australian",
    BASEBALL: "mdi:baseball",
    BASKETBALL: "mdi:basketball",
    CRICKET: "mdi:cricket",
    FOOTBALL: "mdi:football",
    GOLF: "mdi:golf-tee",
    HOCKEY: "mdi:hockey-puck",
    MMA: "mdi:karate",
    RACING: "mdi:flag-checkered",
    RUGBY: "mdi:rugby",
    SOCCER: "mdi:soccer",
    TENNIS: "mdi:tennis",
    VOLLEYBALL: "mdi:volleyball",
}

# Defaults
DEFAULT_CONFERENCE_ID = ""
DEFAULT_ICON = "mdi:scoreboard"
DEFAULT_LEAGUE = "NFL"
DEFAULT_LOGO = (
    "https://cdn0.iconfinder.com/data/icons/shift-interfaces/32/Error-512.png"
)
DEFAULT_NAME = "team_tracker"
DEFAULT_PROB = 0.0
DEFAULT_SPORT_PATH = "UNDEFINED_SPORT"
DEFAULT_TIMEOUT = 120
DEFAULT_LAST_UPDATE = "2022-02-02 02:02:02-05:00"
DEFAULT_KICKOFF_IN = "{test} days"
DEFAULT_REFRESH_RATE = timedelta(minutes=10)
RAPID_REFRESH_RATE = timedelta(seconds=5)

# Services
SERVICE_NAME_CALL_API = "call_api"

# Misc
TEAM_ID = ""
VERSION = "v0.14.9"
ISSUE_URL = "https://github.com/vasqued2/ha-teamtracker"
DOMAIN = "teamtracker"
ATTRIBUTION = "Data provided by ESPN"
COORDINATOR = "coordinator"
PLATFORMS = [Platform.SENSOR]
