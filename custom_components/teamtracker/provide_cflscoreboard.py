""" Provide response from CFL Scoreboard APIs """
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

from .provider_base import BaseSportProvider

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_CFLSCOREBOARD = "cflscoreboard"
CFL_DATA_FORMAT = "cfl-json"
CFLSCOREBOARD_BASE_URL = "https://cflscoreboard.cfl.ca/json/scoreboard"

class CflScoreboardProvider(BaseSportProvider):
    """Provider for CFL Scoreboard data."""
    #
    #  __init__()
    #    Set CFL Scoreboard specific values
    #
    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_CFLSCOREBOARD
        self.data_format = CFL_DATA_FORMAT
        self.ATTRIBUTION: str = "Data provided by cflscoreboard.cfl.ca"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=30)
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

        key = self.DATA_PROVIDER + ":" + sport_path + ":" + league_path

        return key


    #
    #  async_fetch_team_data()
    #    Return a list of team dictionaries
    #      [{
    #        "id": team_id,
    #        "abbreviation": Team Abbreviation
    #        "displayName": Long Team Name
    #        "location": City, State, Country of team
    #        "conference_id": Conference for the team (NCAA Only)
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
        url_parms: dict[str, str] = {}

        url = f"{CFLSCOREBOARD_BASE_URL}/squads.json"
        response = await self.async_call_cflscoreboard_api(hass, url, url_parms, sensor_name, league_path)
        data = response["data"]
        url = response["url"]

        # Build the teams data
        teams = []
        for t in data:
            teams.append({
                "id":            str(t.get("id", "")),
                "abbreviation":  t.get("abbreviation", ""),
                "displayName":   t.get("name", ""),
                "location":      t.get("location", ""),
            })
        return {"data": teams, "url": url}


    #
    #  async_fetch_scoreboard_data()
    #    Call CFL Scoreboard API
    #      1. API will return all games in current season
    #
    async def async_fetch_scoreboard_data(self, hass, lang) -> dict:
        """Gets data from ESPN APIs for specified league."""

        url_parms: dict[str, str] = {}

        if not self._coordinator:
            return{"data": None, "url": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path

        team_id = self._coordinator.team_id.upper()

        url = f"{CFLSCOREBOARD_BASE_URL}/rounds.json"

        response = await self.async_call_cflscoreboard_api(hass, url, url_parms, sensor_name, team_id)

        # Add required lookup tables
        if "team_list" not in self.lookups:
            teams_response = await self.async_fetch_team_data(hass, sport_path, league_path, sensor_name)
            teams_data = teams_response["data"]
            self.lookups["team_list"] = teams_data
        response["lookups"] = self.lookups

        return response

    #
    #  async_call_cflscoreboard_api()
    #
    #    Call an CFL Scoreboard API and get the data returned by it
    #
    async def async_call_cflscoreboard_api(self, hass, base_url, params, sensor_name, team_id, file_override=False) -> dict:
        """Call the specified ESPN API."""

        url = str(URL(base_url).with_query(params))
        _LOGGER.warning(
            "%s: Calling CFL Scoreboard API for '%s': %s",
            sensor_name,
            team_id,
            url,
        )
        timestamp = arrow.now().format(arrow.FORMAT_W3C)

        headers = {
            "User-Agent": self._USER_AGENT,
            "Accept": "application/json",
        }

        session = async_get_clientsession(hass)

        try:
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    try:
                        data = await r.json(content_type=None)
                    except (json.JSONDecodeError, aiohttp.ContentTypeError) as e:
                        text = await r.text()

                        _LOGGER.warning(
                            "%s: CFL Scoreboard response not valid JSON: %s | Body: %s",
                            sensor_name,
                            e,
                            text[:500],
                        )

                        return {
                            "data": None,
                            "url": url,
                            "timestamp": timestamp,
                        }
                else:
                    _LOGGER.warning(
                        "%s: API returned status %s: %s",
                        sensor_name,
                        r.status,
                        url,
                    )

                    return {
                        "data": None,
                        "url": url,
                        "timestamp": timestamp,
                    }

        except (aiohttp.ClientError, TimeoutError) as e:
            _LOGGER.warning("%s: API call failed: %s", sensor_name, e)

            return {
                "data": None,
                "url": url,
                "timestamp": timestamp,
            }

        return {"data": data, "url": url, "timestamp": timestamp}