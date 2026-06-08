""" Provide response from MLBSTATS APIs """
from __future__ import annotations

from datetime import date, timedelta
import json
import logging
from typing import TYPE_CHECKING

import aiohttp
import arrow
import jmespath
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, OVERRIDE_DICT
from .provider_base import BaseSportProvider
from .utils import get_value, is_integer, lookup_actual_team_id

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

#
#  Documentation on the MLB Stat API
#    https://github.com/brianhaferkamp/mlbapidata
#    https://www.reddit.com/r/Sabermetrics/comments/wcf3kr/how_to_get_live_milb_game_data/
#
DATA_PROVIDER_MLBSTATS = "mlbstats"
MLBSTATS_DATA_FORMAT = "mlbstats-json"
MLBSTATS_BASE_URL = "https://statsapi.mlb.com/api"

class MlbStatsProvider(BaseSportProvider):
    """Provider for MLB Stats data."""
    #
    #  __init__()
    #    Set MLB Stats specific values
    #
    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_MLBSTATS
        self.data_format = MLBSTATS_DATA_FORMAT
        self.ATTRIBUTION: str = "Copyright 2026 MLB Advanced Media"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=5)
        self.lookups: dict[str, list] = {}
        self.live_game_pk = None


    #
    #  _get_cache_key()
    #    Return unique key for espn calls
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
    #  _async_fetch_team_data()
    #    Return a list of team dictionaries
    #      [{
    #        "id": team_id,
    #        "displayName": Long Team Name
    #        "abbreviation": Team Abbreviation
    #        "location": City, State, Country of team
    #      }]
    #
    async def _async_fetch_team_data(
        self, 
        hass: HomeAssistant, 
        sport_path: str, 
        league_path: str,
        sensor_name: str,
        ) -> dict:
        """Fetch teams from any API for a given league."""

        rc = await self._async_load_override_dict(hass)    # pylint: disable=unused-variable

        league_abbr = league_path.upper()
        league_config = hass.data.get(DOMAIN, {}).get(OVERRIDE_DICT, {}).get(sport_path.lower(), {}).get(league_path.lower(), None)
        
        if league_config is None:
            _LOGGER.warning(
                "%s: No MLBStats config for league '%s'", sensor_name, league_abbr
            )
            return {"data": None, "url": None, "timestamp": None}

        #
        #   Use the sportId for the league
        #      career = 1, playoffs = 0
        #
        url_parms = {
            "sportId": league_config["sportId"],
        }

        url = f"{MLBSTATS_BASE_URL}/v1/teams"
        response = await self.async_call_mlbstats_api(hass, url, url_parms, sensor_name, league_path)
        data = response["data"]
        url = response["url"]
        timestamp = response["timestamp"]

        if data:
            raw = (
                data.get("teams", [])
            )
        else:
            raw = []

        # Build the teams data
        teams = []
        for t in raw:
#            t = entry.get("team", {})
            teams.append({
                "id":            str(t.get("id", "")),
                "abbreviation":  t.get("abbreviation", ""),
                "displayName":   t.get("name", t.get("teamName", "")),
                "location":      t.get("locationName", ""),
            })
        return {"data": teams, "url": url, "timestamp": timestamp}


    #
    #  _async_fetch_scoreboard_data()
    #    Call MLB Stats API
    #      1. API will return all games for a single day
    #
    async def _async_fetch_scoreboard_data(self, hass, lang) -> dict:
        """Gets data from MLB Stats APIs for specified league."""

        url_parms: dict[str, str] = {}

        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path

        team_id = self._coordinator.team_id

        if "team_list" not in self.lookups:
            teams_response = await self.async_get_team_data(hass, sport_path, league_path, sensor_name)
            team_list = teams_response["data"]
            self.lookups["team_list"] = team_list
        else:
            team_list = self.lookups["team_list"]

        # Incoming team_id is either a team_id or a search term to find the team_id
        #   Searches must be done w/ the actual team_id or a '*'
        search_key = team_id
        if team_id != "*" and not is_integer(team_id):
            search_key = lookup_actual_team_id(sensor_name, team_id, team_list)

        league_config = hass.data.get(DOMAIN, {}).get(OVERRIDE_DICT, {}).get(sport_path.lower(), {}).get(league_path.lower(), None)

        if league_config is None:
            _LOGGER.warning(
                "%s: No MLB Stats config for league '%s'", sensor_name, league_path
            )
            sportId = "UNKNOWN_SPORTID"
        else:
            sportId = league_config["sportId"]

        # If the game from the prior call was not live, get the schedule of games
        if self.live_game_pk is None:
            url = f"{MLBSTATS_BASE_URL}/v1/schedule/games"
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            tomorrow = (date.today() + timedelta(days=1)).isoformat()

            url_parms = {
                "sportId": sportId,
                "startDate": yesterday,
                "endDate": tomorrow,
            }

            response = await self.async_call_mlbstats_api(hass, url, url_parms, sensor_name, team_id)

            data = response.get("data", {})

            # See if there is a live game for the search_key
            #  Get first live instance if "*" else match the team ID
            if search_key == "*":
                query = """
                dates[].games[?status.abstractGameState == 'Live'].gamePk[] | [0]
                """
            else:
                query = f"""
                dates[].games[?status.abstractGameState == 'Live' &&
                            (teams.home.team.id == `{search_key}` ||
                            teams.away.team.id == `{search_key}`)].gamePk[] | [0]
                """

            self.live_game_pk = jmespath.search(query, data)

        # If the game is live, call the API for the live game
        if self.live_game_pk:
            url = f"{MLBSTATS_BASE_URL}/v1.1/game/{self.live_game_pk}/feed/live"
            url_parms = {
                "sportId": sportId,
            }
            response = await self.async_call_mlbstats_api(hass, url, url_parms, sensor_name, team_id)
            response.update({"live_flag": True}) # Add flag to indicate live data so it won't cache

            # If the game is over, the game is no longer live
            status = get_value(response, "data", "gameData", "status", "abstractGameState", default="Final")
            if status == "Final":
                self.live_game_pk = None

        # Add required lookup tables
        response["lookups"] = self.lookups

        return response


    #
    #  async_call_mlbstats_api()
    #
    #    Call an MLB Stats API and get the data returned by it
    #
    async def async_call_mlbstats_api(self, hass, base_url, params, sensor_name, team_id, file_override=False) -> dict:
        """Call the specified MLB Stats API."""

        url = str(URL(base_url).with_query(params))
        _LOGGER.debug(
            "%s: Calling MLBStats API for '%s': %s",
            sensor_name,
            team_id,
            url,
        )
        timestamp = arrow.now().format(arrow.FORMAT_W3C)

        headers = {"User-Agent": self._USER_AGENT}
        session = async_get_clientsession(hass)
        try:
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    try:
                        data = await r.json()
                    except json.JSONDecodeError as e:
                        _LOGGER.debug("%s: MLBStats response not JSON: %s", sensor_name, e)
                        return {"data": None, "url": url, "timestamp": timestamp}
                else:
                    _LOGGER.debug(
                        "%s: API returned status %s: %s", sensor_name, r.status, url
                    )
                    return {"data": None, "url": url, "timestamp": timestamp}
        except (aiohttp.ClientError, TimeoutError) as e:
            _LOGGER.debug("%s: API call failed: %s", sensor_name, e)
            return {"data": None, "url": url, "timestamp": timestamp}

        return {"data": data, "url": url, "timestamp": timestamp}