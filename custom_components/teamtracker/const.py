# API
URL_HEAD = "http://site.api.espn.com/apis/site/v2/sports/"
URL_TAIL = "/scoreboard"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15"

LEAGUE_LIST = [
    ["MLB", "baseball", "mlb"],
    ["NBA", "basketball", "nba"],
    ["WNBA", "basketball", "wnba"],
    ["NCAAM", "basketball", "mens-college-basketball"],
    ["NCAAW", "basketball", "womens-college-basketball"],
    ["NCAAF", "football", "college-football"],
    ["NFL", "football", "nfl"],
    ["NHL", "hockey", "nhl"],
    ["BUND", "soccer", "ger.1"],
    ["CL", "soccer", "uefa.champions"], 
    ["EPL", "soccer", "eng.1"], 
    ["LIGA", "soccer", "esp.1"], 
    ["LIG1", "soccer", "fra.1"], 
    ["MLS", "soccer", "usa.1"], 
    ["NWSL", "soccer", "usa.nwsl"], 
    ["SERA", "soccer", "ita.1"],
    ["WC", "soccer", "fifa.world"],
    ["NCAAVB", "volleyball", "mens-college-volleyball"],
    ["NCAAVBW", "volleyball", "womens-college-volleyball"],
    ]

SPORT_LIST = [
    ["baseball", "mdi:baseball"],
    ["basketball", "mdi:basketball"],
    ["football", "mdi:football"],
    ["hockey", "mdi:hockey-puck"],
    ["soccer", "mdi:soccer"],
    ["volleyball", "mdi:volleyball"]
]

# Config
CONF_CONFERENCE_ID = "conference_id"
CONF_LEAGUE_ID = "league_id"
CONF_LEAGUE_PATH = "league_path"
CONF_SPORT_PATH = "sport_path"
CONF_TIMEOUT = "timeout"
CONF_TEAM_ID = "team_id"

# Defaults
DEFAULT_CONFERENCE_ID = ""
DEFAULT_ICON = "mdi:scoreboard"
DEFAULT_LEAGUE = "NFL"
DEFAULT_LOGO = "https://cdn0.iconfinder.com/data/icons/shift-interfaces/32/Error-512.png"
DEFAULT_LEAGUE_PATH = "league_not_found"
DEFAULT_NAME = "team_tracker"
DEFAULT_PROB = 0.0
DEFAULT_SPORT_PATH = "sport_not_found"
DEFAULT_TIMEOUT = 120

# Misc
TEAM_ID = ""
VERSION = "v0.4.1"
ISSUE_URL = "https://github.com/vasqued2/ha-teamtracker"
DOMAIN = "teamtracker"
PLATFORM = "sensor"
ATTRIBUTION = "Data provided by ESPN"
COORDINATOR = "coordinator"
PLATFORMS = ["sensor"]