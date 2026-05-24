""" Provide response from HockeyTech APIs """
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import locale
import logging
from typing import TYPE_CHECKING, TypedDict

import aiohttp
import arrow
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .provider_base import BaseSportProvider

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_HOCKEYTECH = "hockeytech"
HT_DATA_FORMAT = "ht-json"
HOCKEYTECH_BASE_URL = "https://lscluster.hockeytech.com/feed/index.php"

class HockeyTechLeague(TypedDict):
    public_key: str
    client_code: str
    league_name: str
    league_logo: str | None

class HockeyTechTeamColor(TypedDict):
    color: str
    alternateColor: str
TeamColorMap = dict[str, HockeyTechTeamColor]

#
# HockeyTech API Definitions
#
# Public keys and API documentation provided by:
#    https://mintlify.wiki/Pharaoh-Labs/teamarr/reference/provider-hockeytech
#    https://github.com/IsabelleLefebvre97/PWHL-Data-Reference
#

HOCKEYTECH_LEAGUES: dict[str, HockeyTechLeague]  = {
    "CHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "chl",
        "league_name": "Canadian Hockey League",
        "league_logo": "https://cdn.chl.ca/uploads/chl/2014/05/06154138/CHL.png",
    },
    "OHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "ohl",
        "league_name": "Ontario Hockey League",
        "league_logo": "https://media.chl.ca/wp-content/uploads/sites/5/2023/05/25210408/logo_OHL_lg_white-1.png",
    },
    "WHL": {
        "public_key": "f1aa699db3d81487",
        "client_code": "whl",
        "league_name": "Wester Hockey League",
        "league_logo": "https://media.chl.ca/wp-content/uploads/sites/6/2023/08/18153056/Western_Hockey_League.svg_.png",
    },
    "LHJMQ": {
        "public_key": "f1aa699db3d81487",
        "client_code": "lhjmq",
        "league_name": "Quebec Major Junior Hockey League",
        "league_logo": "https://www.themhl.ca/wp-content/uploads/sites/2/2018/10/QMJHL-Logo.png",
    },
    "AHL": {
        "public_key": "50c2cd9b5e18e390",
        "client_code": "ahl",
        "league_name": "American Hockey League",
        "league_logo": "https://1000logos.net/wp-content/uploads/2023/04/American-Hockey-League-logo-768x432.png",
    },
    "ECHL": {
        "public_key": "2c2b89ea7345cae8",
        "client_code": "echl",
        "league_name": "East Coast Hockey League",
        "league_logo": "https://1000logos.net/wp-content/uploads/2019/01/Echl-logo-768x512.png",
    },
    "PWHL": {
        "public_key": "446521baf8c38984",
        "client_code": "pwhl",
        "league_name": "Professional Womens Hockey League",
        "league_logo": "https://1000logos.net/wp-content/uploads/2024/10/PWHL-Logo.png",
    },
    "USHL": {
        "public_key": "e828f89b243dc43f",
        "client_code": "ushl",
        "league_name": "United States Hockey League",
        "league_logo": "https://dbukjj6eu5tsf.cloudfront.net/ushl.sidearmsports.com/images/responsive_2022/ushl_on-dark.svg",
    },
    "OJHL": {
        "public_key": "77a0bd73d9d363d3",
        "client_code": "ojhl",
        "league_name": "Ontario Junior Hockey League",
        "league_logo": "https://www.ojhl.ca/wp-content/uploads/sites/2/2023/04/default-300x200.jpg",
    },
    "BCHL": {
        "public_key": "ca4e9e599d4dae55",
        "client_code": "bchl",
        "league_name": "British Columbia Hockey League",
        "league_logo": "https://bchl.ca/wp-content/uploads/2015/12/BCHL-Footer-Logo.png",
    },
    "SJHL": {
        "public_key": "2fb5c2e84bf3e4a8",
        "client_code": "sjhl",
        "league_name": "Saskatchewan Junior Hockey League",
        "league_logo": "https://www.sjhl.ca/wp-content/uploads/sites/2/2019/04/cropped-sjhl-512.png",
    },
    "AJHL": {
        "public_key": "cbe60a1d91c44ade",
        "client_code": "ajhl",
        "league_name": "Alberta Junior Hockey League",
        "league_logo": "https://www.ajhl.ca/wp-content/uploads/sites/2/2023/06/ajhl.png",
    },
    "MJHL": {
        "public_key": "f894c324fe5fd8f0",
        "client_code": "mjhl",
        "league_name": "Manitoba Junior Hockey League",
        "league_logo": "https://www.mjhlhockey.ca/wp-content/uploads/sites/2/2024/08/MJHL-8.png",
    },
    "MHL": {
        "public_key": "4a948e7faf5ee58d",
        "client_code": "mhl",
        "league_name": "Maritime Junior Hockey League",
        "league_logo": "https://upload.wikimedia.org/wikipedia/en/thumb/a/a5/Maritime_Junior_A_Hockey_League_Logo.svg/250px-Maritime_Junior_A_Hockey_League_Logo.svg.png",
    },
}
HOCKEYTECH_TEAM_COLORS: dict[str, TeamColorMap] = {
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



class HockeyTechProvider(BaseSportProvider):
    """Provider for HockeyTech data."""

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_HOCKEYTECH
        self.data_format = HT_DATA_FORMAT
        self.ATTRIBUTION: str = "Powered by HockeyTech.com"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=60)


    #
    #  _get_cache_key()
    #    Return unique key for hockteytech calls
    #
    def _get_cache_key(self) -> str:
        """Return cache key"""

        if not self._coordinator:
            return ""

        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        conference_id = self._coordinator.conference_id

        lang = self._coordinator.get_lang()

        key = self.DATA_PROVIDER + ":" + sport_path + ":" + league_path + ":" + conference_id + ":" + lang

        return key

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

        ht_response = await self.async_call_hockeytech_api(hass, HOCKEYTECH_BASE_URL, params, sensor_name, league_abbr)
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

        ht_response = await self.async_call_hockeytech_api(hass, HOCKEYTECH_BASE_URL, params, sensor_name, league_abbr)
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


    async def async_fetch_scoreboard_data(
        self,
        hass,
        lang: str,
    ) -> dict:
        """Fetch scoreboard from HockeyTech API and return ESPN-compatible dict."""

        if not self._coordinator:
            return{"data": None, "url": None}

        sensor_name = self._coordinator.name
        league_path = self._coordinator.league_path
        league_id = league_path.upper()

        league_config = HOCKEYTECH_LEAGUES.get(league_id)

        if league_config is None:
            _LOGGER.warning(
                "%s: No HockeyTech config for league '%s'", sensor_name, league_id
            )
            public_key = "UNKNOWN_PUBLIC_KEY"
            client_code = league_id
        else:
            public_key = league_config["public_key"]
            client_code = league_config["client_code"]

        params = {
            "feed": "modulekit",
            "view": "scorebar",
            "key": public_key,
            "client_code": client_code,
            "lang": lang,
            "fmt": "json",
            "numberofdaysback": 0,
            "numberofdaysahead": 90,
        }

        ht_response = await self.async_call_hockeytech_api(hass, HOCKEYTECH_BASE_URL, params, sensor_name, league_id)
        ht_data = ht_response["ht_data"]
        url = ht_response["url"]
        timestamp = ht_response["timestamp"]

        espn_data = self._transform_hockeytech_to_espn(ht_data, league_id)
        return {
            "data": espn_data,
            "url": url,
            "timestamp": timestamp
        }

    def _transform_hockeytech_to_espn(self, ht_data: dict, league_id: str) -> dict | None:
        """Transform HockeyTech scorebar data into ESPN-compatible format."""

        league_config = HOCKEYTECH_LEAGUES.get(league_id)
        team_colors = HOCKEYTECH_TEAM_COLORS.get(league_id, {})

        if ht_data is None or league_config is None:
            return None
            

        espn_data = {
            "leagues": [
                {
                    "id": league_config.get("client_code", league_id.lower()),
                    "abbreviation": league_id,
                    "logos": [{"href": league_config.get("league_logo", "")}],
                    "name": league_config.get("league_name", ""),
                }
            ],
            "events": [],
        }

        scorebar = ht_data.get("SiteKit", {}).get("Scorebar")
        if not scorebar:
            return espn_data

        for game in scorebar:
            event = self._build_espn_event(game, team_colors)
            if event is not None:
                espn_data["events"].append(event)

        return espn_data


    def _build_espn_event(self, game: dict, team_colors: dict) -> dict | None:
        """Build a single ESPN-format event from a HockeyTech game."""

        game_id = game.get("ID", "")
        espn_date = self._convert_to_espn_date(game.get("GameDateISO8601", ""))
        if not espn_date:
            return None

        state = _STATUS_MAP.get(game.get("GameStatus", "1"), "pre")
        short_detail = self._build_short_detail(game, state)
        period = 0
        try:
            period = int(game.get("Period", 0))
        except (ValueError, TypeError):
            pass

        home_competitor = self._build_competitor(game, "Home", "home", team_colors)
        visitor_competitor = self._build_competitor(game, "Visitor", "away", team_colors)

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
        venue = self._build_venue(game)

        event = {
            "id": game_id,
            "date": espn_date,
            "name": f'{game.get("VisitorLongName", "")} at {game.get("HomeLongName", "")}',
            "shortName": f'{game.get("VisitorCode", "")} @ {game.get("HomeCode", "")}',
            "season": {"slug": "regular-season"},
            "links": [{"href": f'{game.get("FloHockeyUrl", "")}'}],
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


    def _build_competitor(self, game: dict, side: str, home_away: str, team_colors: dict) -> dict:
        """Build an ESPN-format competitor from HockeyTech game data.

        side: "Home" or "Visitor" (HockeyTech field prefix)
        home_away: "home" or "away" (ESPN value)
        """

        team_code = game.get(f"{side}Code", "")
        team_id = game.get(f"{side}ID", "")
        colors = team_colors.get(team_code, {})
        team_url = game.get(f"{side}WebcastUrl", "")
        if team_url == "":
            team_url = game.get(f"{side}VideoUrl", "")
        if team_url == "":
            team_url = game.get(f"{side}AudioUrl", "")

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
                "links": [{"href": f"{team_url}"}],
            },
            "records": [
                {
                    "summary": self._format_record(game, side),
                }
            ],
            "statistics": [],
        }


    def _format_record(self, game: dict, side: str) -> str:
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


    def _convert_to_espn_date(self, iso_str: str) -> str:
        """Convert HockeyTech ISO8601 date to ESPN date format (e.g., 2026-03-19T23:00Z)."""

        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str)
            dt_utc = dt.astimezone(timezone.utc)
            return dt_utc.strftime("%Y-%m-%dT%H:%MZ")
        except (ValueError, TypeError):
            return ""


    def _build_short_detail(self, game: dict, state: str) -> str:
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


    def _build_venue(self, game: dict) -> dict:
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


    async def async_call_hockeytech_api(self, hass, base_url, params, sensor_name, league_id) -> dict:
        """Call the HockeyTech API.
            Response:
            {
                "ht_data": JSON reponse from API or None
                "url:      URL for the call
            }
        """
        headers = {"User-Agent": self._USER_AGENT}
        session = async_get_clientsession(hass)

        url = str(URL(base_url).with_query(params))

        _LOGGER.debug(
            "%s: Calling HockeyTech API: %s",
            sensor_name,
            url,
        )
        timestamp = arrow.now().format(arrow.FORMAT_W3C)

        try:
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    text = await r.text()
                else:
                    _LOGGER.debug(
                        "%s: HockeyTech API returned status %s", sensor_name, r.status
                    )
                    return {"ht_data": None, "url": url, "timestamp": timestamp}
        except (aiohttp.ClientError, TimeoutError) as e:
            _LOGGER.debug("%s: HockeyTech API call failed: %s", sensor_name, e)
            return {"ht_data": None, "url": url, "timestamp": timestamp}


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
            _LOGGER.debug("%s: HockeyTech response not JSON: %s", sensor_name, e)
            ht_data = None

        return {
            "ht_data": ht_data,
            "url": url,
            "timestamp": timestamp
        }