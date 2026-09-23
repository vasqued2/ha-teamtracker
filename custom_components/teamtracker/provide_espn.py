""" Provide response from ESPN APIs """
from __future__ import annotations

from datetime import timedelta
import json
import logging
import os
from typing import TYPE_CHECKING

import aiofiles
import aiohttp
import arrow
import jmespath
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_LIMIT
from .provider_base import BaseSportProvider

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_ESPN = "espn"
ESPN_DATA_FORMAT = "espn-json"
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"

class EspnProvider(BaseSportProvider):
    """Provider for ESPN data."""
    #
    #  __init__()
    #    Set ESPN specific values
    #
    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_ESPN
        self.data_format = ESPN_DATA_FORMAT
        self.ATTRIBUTION: str = "Data provided by ESPN"
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

        url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/teams"
        url_parms = {"limit": 1000}
        response = await self.async_call_espn_api(hass, url, url_parms, sensor_name, league_path)
        data = response["data"]
        url = response["url"]
        timestamp = response["timestamp"]

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
            })
        return {"data": teams, "url": url, "timestamp": timestamp}


    async def async_get_team_conference_id(
        self,
        hass: HomeAssistant, 
        sport_path: str, 
        league_path: str, 
        team_id: str
    ) -> str:
        """Fetch conference/group ID for a single team from the ESPN team detail API."""

        url = (
            f"{ESPN_BASE_URL}/{sport_path}/{league_path}/teams/{team_id}"
        )
        response = await self.async_call_espn_api(hass, url, None, "ConfigFlow-teamGroup", team_id)
        data = response["data"]
        if data:
            groups = data.get("team", {}).get("groups") or {}
            return str(groups.get("id", ""))
        return str("")



    #
    #  _async_fetch_scoreboard_data()
    #    Call ESPN API with using varying date ranges and parameters until events returned
    #      1. Call scoreboard API w/ default date range
    #      2. Call teams API to get nextEvent
    #      3. Call scoreboard API w/o language parm (some sports not returned in some languages)
    #
    async def _async_fetch_scoreboard_data(self, hass, lang) -> dict:
        """Gets data from ESPN APIs for specified league."""

        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        team_id = self._coordinator.team_id.upper()

        # Add required lookup tables
        if "team_list" not in self.lookups:
            teams_response = await self.async_get_team_data(hass, sport_path, league_path, sensor_name)
            teams_data = teams_response["data"]
            self.lookups["team_list"] = teams_data

        # Set team_number if not already set
        if self._coordinator.team_number is None:
            self._coordinator.team_number = "unknown"
            if (isinstance(team_id, int)) or (isinstance(team_id, str) and team_id.isdigit()):
                self._coordinator.team_number = str(team_id)
            else:
                for t in teams_data:
                    if (t["abbreviation"].upper() == team_id):
                        self._coordinator.team_number = t["id"]
                        break

        url_parms = {}
        url_parms["lang"] = lang[:2]
        url_parms["limit"] = str(API_LIMIT)

        file_override = False
        if self._coordinator.conference_id:
            url_parms["groups"] = self._coordinator.conference_id
            if self._coordinator.conference_id == "9999":
                file_override = True

        url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/scoreboard"

        response = await self.async_call_espn_api(hass, url, url_parms, sensor_name, team_id, file_override)
        data = response["data"]
        url = response["url"]

        num_events = 0
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            num_events = len(data["events"])

        # First fallback - without language
        if num_events == 0:
            url_parms.pop("lang", None)
            url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/scoreboard"
            _LOGGER.debug(
                "%s: Calling API without language for '%s' from %s",
                sensor_name,
                team_id,
                url,
            )
            response = await self.async_call_espn_api(hass, url, url_parms, sensor_name, team_id)

        num_events = 0
        team_found = False
        if data is not None:
            _LOGGER.debug(
                "%s: Data returned for '%s' from %s",
                sensor_name,
                league_path,
                url,
            )
            if isinstance(data, dict) and isinstance(data.get("events"), list):
                num_events = len(data["events"])
                team_match = jmespath.search(
                        f"events[].competitions[].competitors[?team.abbreviation == '{team_id}' || team.id == '{team_id}'][]",
                        data,)
                team_found = bool(team_match)
            else:
                num_events = 0
                _LOGGER.exception("%s: Error processing ESPN data", sensor_name)

        # Second fallback - Teams API if team_number is known
        if num_events == 0 or team_found is False:
            team_number = self._coordinator.team_number
            if (isinstance(team_number, int)) or (isinstance(team_number, str) and team_number.isdigit()):

                url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/teams/{self._coordinator.team_number}"

                response2 = await self.async_get_teams_teamnumber_data(hass, lang)
                data = response2["data"]
                url = response2["url"]

                if data is not None:
                    team_match = jmespath.search(
                            f"team.nextEvent[0].competitions[0].competitors[?id == '{team_number}'].id | [0]",
                            data,)
                    if bool(team_match):
                        num_events = 1
                        # The teams API doesn't have leagues info so insert it from first call
                        if "leagues" in response["data"]:
                            response2["data"]["leagues"] = response["data"]["leagues"]
                        response = response2

                _LOGGER.debug(
                    "%s: Num_events '%d' from %s",
                    sensor_name,
                    num_events,
                    url,
                )

        response["lookups"] = self.lookups
        return response


    #
    #  async_get_teams_teamnumber_data()
    #    Return data from cache or call fetch if needed
    #
    async def async_get_teams_teamnumber_data(
        self, 
        hass: HomeAssistant, 
        lang: str,
        ) -> dict:
        """Return data from cache and call fetch if needed."""
        CACHE_NAME = "teams_teamnumber_data"
        CACHE_DURATION = timedelta(hours=1)

        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        team_number = self._coordinator.team_number

        #  If cached, return response
        key = f"{self.DATA_PROVIDER}:{sport_path}:{league_path}:{team_number}:{lang}"
        response = self._get_from_cache(CACHE_NAME, key, CACHE_DURATION)
        if response:
            response.update({"cache_flag": True}) # Add key to indicate cache was used
            return response

        # Fetch data and save to cache
        response = await self._async_fetch_teams_teamnumber_data(hass, lang)
        
        if not response.get("live_flag", False):
            self._save_to_cache(CACHE_NAME, key, response)

        return response



    #
    #  _async_fetch_teams_teamnumber_data()
    #
    async def _async_fetch_teams_teamnumber_data(
        self, 
        hass: HomeAssistant, 
        lang: str,
        ) -> dict:
        """Fetch team-specific data from teams API."""

        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        team_number = self._coordinator.team_number

        if team_number is None or team_number.isdigit() is False:
            return {"data": None, "url": None, "timestamp": None}

        url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/teams/{team_number}"
        url_parms = {}
        url_parms["lang"] = lang[:2]
        response = await self.async_call_espn_api(hass, url, url_parms, sensor_name, league_path)

        return response


    #
    #  async_call_espn_api()
    #
    #    Call an ESPN API (or use file w/ the appropriate file override) and get the data returned by it
    #
    async def async_call_espn_api(self, hass, base_url, params, sensor_name, team_id, file_override=False) -> dict:
        """Call the specified ESPN API."""

        url = str(URL(base_url).with_query(params))
        _LOGGER.debug(
            "%s: Calling ESPN API for '%s': %s",
            sensor_name,
            team_id,
            url,
        )
        timestamp = arrow.now().format(arrow.FORMAT_W3C)

        if file_override:
            data = await self._async_override_espn_api(sensor_name, team_id, base_url)
            return {"data": data, "url": url, "timestamp": timestamp}


        headers = {
#            "User-Agent": self._USER_AGENT, 
            "Accept": "application/ld+json"}
        session = async_get_clientsession(hass)
        try:
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    try:
                        data = await r.json()
                    except json.JSONDecodeError as e:
                        _LOGGER.debug("%s: HockeyTech response not JSON: %s", sensor_name, e)
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


    #
    #  Call an ESPN API (or file use the appropriate file override) and get the data returned by it
    #    This utility will eventually replace/wrap all API calls
    #
    async def _async_override_espn_api(self, sensor_name, team_id, url) -> dict | None:
        """Read a json file to mock the ESPN API."""

        _LOGGER.debug("%s: Overriding API for '%s'", sensor_name, team_id)

        if sensor_name == "api_error":
            return None

        clean_url = url.split('?')[0]

        _LOGGER.debug("%s: Overriding ESPN API (%s) for '%s'", sensor_name, url, team_id)
        if "schedule" in clean_url:
            file_path = "/share/tt/schedule.json"
            if not os.path.exists(file_path):
                file_path = "tests/tt/schedule.json"
        elif "teams" in clean_url:
            if clean_url[-1].isdigit(): # if there is any team identifier, use team 194
                file_path = "/share/tt/teams-194.json"
                if not os.path.exists(file_path):
                    file_path = "tests/tt/teams-194.json"
            elif "football" in clean_url:
                file_path = "/share/tt/teams-ncaaf-small.json"
                if not os.path.exists(file_path):
                    file_path = "tests/tt/teams-ncaaf-small.json"
            else:
                file_path = "/share/tt/teams.json"
                if not os.path.exists(file_path):
                    file_path = "tests/tt/team.json"
        elif "/all/" in clean_url:
            file_path = "/share/tt/scoreboard_all_leagues.json"
            if not os.path.exists(file_path):
                file_path = "tests/tt/scoreboard_all_leagues.json"
        else:
            file_path = "/share/tt/all.json"
            if not os.path.exists(file_path):
                file_path = "tests/tt/all.json"

        try:
            async with aiofiles.open(file_path, mode="r") as f:
                contents = await f.read()
            data = json.loads(contents)
        except Exception as e: # pylint: disable=broad-exception-caught
            _LOGGER.debug("%s: API file read failed: %s", sensor_name, e)
            data = None

        return(data)