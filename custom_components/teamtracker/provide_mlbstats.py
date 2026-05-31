""" Provide response from MLBSTATS APIs """
from __future__ import annotations

from datetime import timedelta
import json
import logging
from typing import TYPE_CHECKING

import aiohttp
import arrow
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, OVERRIDE_DICT
from .provider_base import BaseSportProvider

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_MLBSTATS = "mlbstats"
MLBSTATS_DATA_FORMAT = "mlbstats-json"
MLBSTATS_BASE_URL = "http://statsapi.mlb.com/api/v1"

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
    #  async_fetch_team_data()
    #    Return a list of team dictionaries
    #      [{
    #        "id": team_id,
    #        "displayName": Long Team Name
    #        "abbreviation": Team Abbreviation
    #        "location": City, State, Country of team
    #      }]
    #
    async def async_fetch_team_data(
        self, 
        hass: HomeAssistant, 
        sport_path: str="", 
        league_path: str="",
        sensor_name: str= "ConfigFlow-teams"
        ) -> dict:
        """Fetch teams from any API for a given league."""

        rc = await self._async_load_override_dict(hass)    # pylint: disable=unused-variable

        league_abbr = league_path.upper()
        league_config = hass.data.get(DOMAIN, {}).get(OVERRIDE_DICT, {}).get(sport_path.lower(), {}).get(league_path.lower(), None)
        
        if league_config is None:
            _LOGGER.warning(
                "%s: No MLBStats config for league '%s'", sensor_name, league_abbr
            )
            return {"data": None, "url": None}

        #
        #   Use the sportId for the league
        #      career = 1, playoffs = 0
        #
        url_parms = {
            "sportId": league_config["sportId"],
        }

        url = f"{MLBSTATS_BASE_URL}/teams"
        response = await self.async_call_mlbstats_api(hass, url, url_parms, sensor_name, league_path)
        data = response["data"]
        url = response["url"]
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
        return {"data": teams, "url": url}


    #
    #  async_fetch_scoreboard_data()
    #    Call MLB Stats API
    #      1. API will return all games for a single day
    #
    async def async_fetch_scoreboard_data(self, hass, lang) -> dict:
        """Gets data from MLB Stats APIs for specified league."""

        url_parms: dict[str, str] = {}

        if not self._coordinator:
            return{"data": None, "url": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path

        team_id = self._coordinator.team_id.upper()

        league_config = hass.data.get(DOMAIN, {}).get(OVERRIDE_DICT, {}).get(sport_path.lower(), {}).get(league_path.lower(), None)

        if league_config is None:
            _LOGGER.warning(
                "%s: No HockeyTech config for league '%s'", sensor_name, league_path
            )
            sportId = "UNKNOWN_SPORTID"
        else:
            sportId = league_config["sportId"]

        url = f"{MLBSTATS_BASE_URL}/games"
        url_parms = {
            "sportId": sportId,
        }

        response = await self.async_call_mlbstats_api(hass, url, url_parms, sensor_name, team_id)

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

        headers = {"User-Agent": self._USER_AGENT, "Accept": "application/ld+json"}
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