""" Provide response from HockeyTech APIs """
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import locale
import logging
import os
from typing import TYPE_CHECKING

import aiohttp
import arrow
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, OVERRIDE_DICT
from .provider_base import BaseSportProvider
from .utils import load_file_overrides

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

#
# HockeyTech API Definitions
#
# Public keys and API documentation provided by:
#    https://mintlify.wiki/Pharaoh-Labs/teamarr/reference/provider-hockeytech
#    https://github.com/IsabelleLefebvre97/PWHL-Data-Reference
#
DATA_PROVIDER_HOCKEYTECH = "hockeytech"
HT_DATA_FORMAT = "ht-json"
HOCKEYTECH_BASE_URL = "https://lscluster.hockeytech.com/feed/index.php"

class HockeyTechProvider(BaseSportProvider):
    """Provider for HockeyTech data."""

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_HOCKEYTECH
        self.data_format = HT_DATA_FORMAT
        self.ATTRIBUTION: str = "Powered by HockeyTech.com"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=60)
        self.lookups: dict[str, list] = {}


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
    #   "abbreviation": Team Abbreviation
    #   "location": City, State, Country of team
    #  }]
    #
    async def async_fetch_team_data(
        self, 
        hass: HomeAssistant, 
        sport_path: str="", 
        league_path: str ="",
        sensor_name: str= "ConfigFlow-teams"
        ) -> dict:
        """Fetch teams from any API for a given league."""

        # Initialize DOMAIN in hass.data if it doesn't exist
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}

        if OVERRIDE_DICT not in hass.data[DOMAIN]:
            hass.data[DOMAIN][OVERRIDE_DICT] = None
            component_dir = os.path.dirname(__file__)
            default_file = os.path.join(component_dir, "overrides", "default.json")
            custom_file = hass.config.path("teamtracker_overrides.json")

            override_dict = await hass.async_add_executor_job(
                load_file_overrides, default_file, custom_file
            )
            
            if OVERRIDE_DICT not in hass.data[DOMAIN] or hass.data[DOMAIN][OVERRIDE_DICT] is None:
                hass.data[DOMAIN][OVERRIDE_DICT] = override_dict

        league_abbr = league_path.upper()
        league_config = hass.data.get(DOMAIN, {}).get(OVERRIDE_DICT, {}).get(sport_path.lower(), {}).get(league_path.lower(), None)
        
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
            })
        return {"data": teams, "url": url}


    #
    #  async_fetch_scoreboard_data()
    #
    async def async_fetch_scoreboard_data(
        self,
        hass,
        lang: str,
    ) -> dict:
        """Fetch scoreboard from HockeyTech API and return ESPN-compatible dict."""

        if not self._coordinator:
            return{"data": None, "url": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        league_id = league_path.upper()

        league_config = hass.data.get(DOMAIN, {}).get(OVERRIDE_DICT, {}).get(sport_path.lower(), {}).get(league_path.lower(), None)

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

        # Add required lookup tables
        if "team_list" not in self.lookups:
            teams_response = await self.async_fetch_team_data(hass, sport_path, league_path, sensor_name)
            teams_data = teams_response["data"]
            self.lookups["team_list"] = teams_data

        return {
            "data": espn_data,
            "lookups": self.lookups,
            "url": url,
            "timestamp": timestamp
        }


    #
    #  _transform_hockeytech_to_espn()
    #
    def _transform_hockeytech_to_espn(self, ht_data: dict, league_id: str) -> dict | None:
        """Transform HockeyTech scorebar data into ESPN-compatible format."""

        if self._coordinator is None:
            return None

        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path

        league_config = self._coordinator.hass.data.get(DOMAIN, {}).get(OVERRIDE_DICT, {}).get(sport_path.lower(), {}).get(league_path.lower(), None)

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
            event = self._build_espn_event(game)
            if event is not None:
                espn_data["events"].append(event)

        return espn_data


    #
    #  _build_espn_event()
    #
    def _build_espn_event(self, game: dict) -> dict | None:
        """Build a single ESPN-format event from a HockeyTech game."""

        # HockeyTech GameStatus codes
        _STATUS_MAP = {
            "1": "pre",
            "2": "in",
            "3": "in",   # Intermission is still "in progress"
            "4": "post",
        }

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

        home_competitor = self._build_competitor(game, "Home", "home")
        visitor_competitor = self._build_competitor(game, "Visitor", "away")

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


    #
    #  _build_competitor()
    #
    def _build_competitor(self, game: dict, side: str, home_away: str) -> dict:
        """Build an ESPN-format competitor from HockeyTech game data.

        side: "Home" or "Visitor" (HockeyTech field prefix)
        home_away: "home" or "away" (ESPN value)
        """

        team_code = game.get(f"{side}Code", "")
        team_id = game.get(f"{side}ID", "")
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
                "color": "D3D3D3",
                "alternateColor": "A9A9A9",
                "links": [{"href": f"{team_url}"}],
            },
            "records": [
                {
                    "summary": self._format_record(game, side),
                }
            ],
            "statistics": [],
        }


    #
    #  _format_record()
    #
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


    #
    #  _convert_to_espn_date()
    #
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


    #
    #  _build_short_detail()
    #
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


    #
    #  _build_venue()
    #
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


    #
    #  async_call_hockeytech_api()
    #
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