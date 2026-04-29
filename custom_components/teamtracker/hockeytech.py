"""HockeyTech API client and ESPN format transformer for TeamTracker."""

import json
import logging
from datetime import datetime, timezone
from yarl import URL

import aiohttp

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

#
# HockeyTech API Definitions
#
# Public keys and API documentation provided by:
#    https://www.mintlify.com/Pharaoh-Labs/teamarr/reference/provider-hockeytech
#    https://github.com/IsabelleLefebvre97/PWHL-Data-Reference
#
DATA_PROVIDER_HOCKEYTECH = "hockeytech"
ATTRIBUTION_HOCKEYTECH = "Powered by HockeyTech.com"
HOCKEYTECH_BASE_URL = "https://lscluster.hockeytech.com/feed/index.php"
HOCKEYTECH_LEAGUES = {
    "CHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "chl",
        "leage_name": "Canadian Hockey League",
        "league_logo": None,
    },
    "OHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "ohl",
        "leage_name": "Ontario Hockey League",
        "league_logo": None,
    },
    "WHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "whl",
        "leage_name": "Wester Hockey League",
        "league_logo": None,
    },
    "QMJHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "qmjhl",
        "leage_name": "Quebec Major Junior Hockey League",
        "league_logo": None,
    },
    "AHL": {
        "public_key": "50c2cd9b5e18e390",
        "client_code": "ahl",
        "leage_name": "American Hockey League",
        "league_logo": None,
    },
    "ECHL": {
        "public_key": "2c2b89ea7345cae8",
        "client_code": "echl",
        "leage_name": "East Coast Hockey League",
        "league_logo": None,
    },
    "PWHL": {
        "public_key": "446521baf8c38984",
        "client_code": "pwhl",
        "leage_name": "Professional Womens Hockey League",
        "league_logo": "https://assets.leaguestat.com/pwhl/logos/pwhl.png",
    },
    "USHL": {
        "public_key": "e828f89b243dc43f",
        "client_code": "ushl",
        "leage_name": "United States Hockey League",
        "league_logo": None,
    },
    "OJHL": {
        "public_key": "77a0bd73d9d363d3",
        "client_code": "ojhl",
        "leage_name": "Ontario Junior Hockey League",
        "league_logo": None,
    },
    "BCHL": {
        "public_key": "ca4e9e599d4dae55",
        "client_code": "bchl",
        "leage_name": "British Columbia Hockey League",
        "league_logo": None,
    },
    "SJHL": {
        "public_key": "2fb5c2e84bf3e4a8",
        "client_code": "sjhl",
        "leage_name": "Saskatchewan Junior Hockey League",
        "league_logo": None,
    },
    "AJHL": {
        "public_key": "cbe60a1d91c44ade",
        "client_code": "ajhl",
        "leage_name": "Alberta Junior Hockey League",
        "league_logo": None,
    },
    "MJHL": {
        "public_key": "f894c324fe5fd8f0",
        "client_code": "mjhl",
        "leage_name": "Manitoba Junior Hockey League",
        "league_logo": None,
    },
    "MHL": {
        "public_key": "4a948e7faf5ee58d",
        "client_code": "mhl",
        "leage_name": "Maritime Junior Hockey League",
        "league_logo": None,
    },
}
HOCKEYTECH_TEAM_COLORS = {
    "PWHL": {
        "BOS": {"color": "1a3c34", "alternateColor": "f0c744"},
        "MIN": {"color": "2e1a47", "alternateColor": "ffffff"},
        "MTL": {"color": "862633", "alternateColor": "ffffff"},
        "NY":  {"color": "00b2e2", "alternateColor": "e8421e"},
        "OTT": {"color": "c8102e", "alternateColor": "000000"},
        "TOR": {"color": "006bae", "alternateColor": "ffffff"},
        "SEA": {"color": "002d72", "alternateColor": "69b3e7"},
        "VAN": {"color": "004c3f", "alternateColor": "c4a24b"},
    },
}



# HockeyTech GameStatus codes
_STATUS_MAP = {
    "1": "pre",
    "2": "in",
    "3": "in",   # Intermission is still "in progress"
    "4": "post",
}


async def async_fetch_hockeytech_scoreboard(
    hass,
    league_id: str,
    sensor_name: str,
) -> dict | None:
    """Fetch scoreboard from HockeyTech API and return ESPN-compatible dict."""

    league_config = HOCKEYTECH_LEAGUES.get(league_id.upper())
    if league_config is None:
        _LOGGER.warning(
            "%s: No HockeyTech config for league '%s'", sensor_name, league_id
        )
        return None

    params = {
        "feed": "modulekit",
        "view": "scorebar",
        "key": league_config["public_key"],
        "client_code": league_config["client_code"],
        "lang": "en",
        "fmt": "json",
        "numberofdaysback": 0,
        "numberofdaysahead": 90,
    }

    ht_response = await async_call_hockeytech_api(hass, params, sensor_name, league_id)
    ht_data = ht_response["ht_data"]
    url = ht_response["url"]

    espn_data = _transform_hockeytech_to_espn(ht_data, league_id)
    return {
        "data": espn_data,
        "url": url
    }


def _transform_hockeytech_to_espn(ht_data: dict, league_id: str) -> dict:
    """Transform HockeyTech scorebar data into ESPN-compatible format."""

    if ht_data is None:
        return None
        
    league_config = HOCKEYTECH_LEAGUES.get(league_id, {})
    team_colors = HOCKEYTECH_TEAM_COLORS.get(league_id, {})

    espn_data = {
        "leagues": [
            {
                "id": league_config.get("client_code", league_id.lower()),
                "abbreviation": league_id,
                "logos": [{"href": league_config.get("league_logo", "")}],
            }
        ],
        "events": [],
    }

    scorebar = ht_data.get("SiteKit", {}).get("Scorebar")
    if not scorebar:
        return espn_data

    for game in scorebar:
        event = _build_espn_event(game, team_colors)
        if event is not None:
            espn_data["events"].append(event)

    return espn_data


def _build_espn_event(game: dict, team_colors: dict) -> dict | None:
    """Build a single ESPN-format event from a HockeyTech game."""

    game_id = game.get("ID", "")
    espn_date = _convert_to_espn_date(game.get("GameDateISO8601", ""))
    if not espn_date:
        return None

    state = _STATUS_MAP.get(game.get("GameStatus", "1"), "pre")
    short_detail = _build_short_detail(game, state)
    period = 0
    try:
        period = int(game.get("Period", 0))
    except (ValueError, TypeError):
        pass

    home_competitor = _build_competitor(game, "Home", "home", team_colors)
    visitor_competitor = _build_competitor(game, "Visitor", "away", team_colors)

    # Determine winners for POST state
    if state == "post":
        try:
            home_goals = int(game.get("HomeGoals", 0))
            visitor_goals = int(game.get("VisitorGoals", 0))
            home_competitor["winner"] = home_goals > visitor_goals
            visitor_competitor["winner"] = visitor_goals > home_goals
        except (ValueError, TypeError):
            pass

    # Parse venue
    venue = _build_venue(game)

    # Broadcasts
    broadcasts = []
    video_url = game.get("HomeVideoUrl", "")
    if video_url:
        broadcasts = [{"names": ["PWHL Live"]}]

    event = {
        "id": game_id,
        "date": espn_date,
        "name": f'{game.get("VisitorLongName", "")} at {game.get("HomeLongName", "")}',
        "shortName": f'{game.get("VisitorCode", "")} @ {game.get("HomeCode", "")}',
        "season": {"slug": "regular-season"},
        "links": [{"href": f"https://www.thepwhl.com/en/game/{game_id}"}],
        "status": {
            "clock": 0,
            "period": period,
            "type": {
                "state": state,
                "shortDetail": short_detail,
            },
        },
        "competitions": [
            {
                "id": game_id,
                "date": espn_date,
                "venue": venue,
                "competitors": [home_competitor, visitor_competitor],
                "broadcasts": broadcasts,
                "status": {
                    "period": period,
                    "type": {
                        "state": state,
                        "shortDetail": short_detail,
                    },
                },
                "odds": [],
            }
        ],
    }

    return event


def _build_competitor(game: dict, side: str, home_away: str, team_colors: dict) -> dict:
    """Build an ESPN-format competitor from HockeyTech game data.

    side: "Home" or "Visitor" (HockeyTech field prefix)
    home_away: "home" or "away" (ESPN value)
    """

    team_code = game.get(f"{side}Code", "")
    team_id = game.get(f"{side}ID", "")
    colors = team_colors.get(team_code, {})

    return {
        "id": team_id,
        "type": "team",
        "order": 0 if home_away == "home" else 1,
        "homeAway": home_away,
        "winner": None,
        "score": game.get(f"{side}Goals", "0"),
        "team": {
            "id": team_id,
            "abbreviation": team_code,
            "displayName": game.get(f"{side}LongName", ""),
            "shortDisplayName": game.get(f"{side}Nickname", ""),
            "logo": game.get(f"{side}Logo", ""),
            "color": colors.get("color", "D3D3D3"),
            "alternateColor": colors.get("alternateColor", "A9A9A9"),
            "links": [{"href": f"https://www.thepwhl.com/en/team/{team_id}"}],
        },
        "records": [
            {
                "summary": _format_record(game, side),
            }
        ],
        "statistics": [],
    }


def _format_record(game: dict, side: str) -> str:
    """Format W-L-OTL record string from HockeyTech fields."""

    wins = game.get(f"{side}Wins", "0")
    reg_losses = game.get(f"{side}RegulationLosses", "0")
    try:
        ot_losses = int(game.get(f"{side}OTLosses", "0")) + int(
            game.get(f"{side}ShootoutLosses", "0")
        )
    except (ValueError, TypeError):
        ot_losses = 0
    return f"{wins}-{reg_losses}-{ot_losses}"


def _convert_to_espn_date(iso_str: str) -> str:
    """Convert HockeyTech ISO8601 date to ESPN date format (e.g., 2026-03-19T23:00Z)."""

    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime("%Y-%m-%dT%H:%MZ")
    except (ValueError, TypeError):
        return ""


def _build_short_detail(game: dict, state: str) -> str:
    """Build the status shortDetail string based on game state."""

    if state == "post":
        detail = game.get("GameStatusStringLong", "Final")
        # Check for OT/SO
        try:
            period = int(game.get("Period", 3))
            if period > 3:
                detail = "Final/OT"
        except (ValueError, TypeError):
            pass
        return detail

    if state == "in":
        clock = game.get("GameClock", "")
        period_name = game.get("PeriodNameLong", "")
        intermission = game.get("Intermission", "0")
        if intermission == "1":
            return f"End of {period_name}"
        if clock and period_name:
            return f"{clock} - {period_name}"
        return game.get("GameStatusStringLong", "In Progress")

    # PRE state
    time_str = game.get("ScheduledFormattedTime", "")
    tz_str = game.get("TimezoneShort", "")
    if time_str:
        return f"{time_str} {tz_str}".strip()
    return game.get("GameDateISO8601", "")


def _build_venue(game: dict) -> dict:
    """Build ESPN-format venue dict from HockeyTech game data."""

    venue_name = game.get("venue_name", "")
    # venue_name can contain "Venue | City" format
    if " | " in venue_name:
        venue_name = venue_name.split(" | ")[0].strip()

    venue_location = game.get("venue_location", "")
    city = ""
    state = ""
    if ", " in venue_location:
        parts = venue_location.split(", ", 1)
        city = parts[0]
        state = parts[1] if len(parts) > 1 else ""

    return {
        "fullName": venue_name,
        "address": {
            "city": city,
            "state": state,
        },
    }


async def async_call_hockeytech_api(hass, params, sensor_name, league_id) -> dict:
    """Call the HockeyTech API.
        Response:
        {
            "ht_data": JSON reponse from API or None
            "url:      URL for the call
        }
    """
    headers = {"User-Agent": USER_AGENT}
    session = async_get_clientsession(hass)

    url = str(URL(HOCKEYTECH_BASE_URL).with_query(params))

    _LOGGER.debug(
        "%s: Calling HockeyTech API: %s",
        sensor_name,
        url,
    )
    try:
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                _LOGGER.warning(
                    "%s: HockeyTech API returned status %s", sensor_name, r.status
                )
                return {"ht_data": None, "url": url}
            text = await r.text()
    except (aiohttp.ClientError, TimeoutError) as e:
        _LOGGER.warning("%s: HockeyTech API call failed: %s", sensor_name, e)
        return {"ht_data": None, "url": url}


    # Strip JSONP wrapper if present
    text = text.strip()
    if text.startswith("("):
        text = text[1:]
    if text.endswith(");"):
        text = text[:-2]
    elif text.endswith(")"):
        text = text[:-1]

    try:
        ht_data = json.loads(text)
    except json.JSONDecodeError as e:
        _LOGGER.warning("%s: HockeyTech response not JSON: %s", sensor_name, e)
        ht_data = None

    return {
        "ht_data": ht_data,
        "url": url
    }
