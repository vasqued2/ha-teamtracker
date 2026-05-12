from __future__ import annotations

import aiofiles
import aiohttp
from datetime import date, timedelta
import json
import logging
import os
from typing import TYPE_CHECKING
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .base_provider import BaseSportProvider
from .const import (
    API_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_ESPN = "espn"
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
        self.ATTRIBUTION: str = "Data provided by ESPN"
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(seconds=5)

    #
    #  async_fetch_team_data()
    #    Return a list of team dictionaries
    #      [{
    #        "id": team_id,
    #        "displayName": Long Team Name
    #        "location": City, State, Country of team
    #        "conference_id": Conference for the team (NCAA Only)
    #      }]
    #
    async def async_fetch_team_data(self, hass: HomeAssistant, sport_path: str="", league_path: str="") -> dict:
        """Fetch teams from any API for a given league."""

        url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/teams"
        url_parms = {"limit": 1000}
        response = await self.async_call_espn_api(hass, url, url_parms, "ConfigFlow-teams", league_path)
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


    async def async_fetch_team_conference_id(
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
    #  async_fetch_scoreboard_data()
    #    Call ESPN API with using varying date ranges and parameters until events returned
    #      1. Call w/ sport specific date range
    #      2. Call w/o date range specfied (uses ESPN default behavior)
    #      3. Call w/o language parm (some sports not returned in some languages)
    #
    async def async_fetch_scoreboard_data(self, hass, lang) -> dict:
        """Gets data from ESPN APIs for specified league."""

        if not self._coordinator:
            return{"data": None, "url": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        team_id = self._coordinator.team_id.upper()

        url_parms = {}
        url_parms["lang"] = lang[:2]
        url_parms["limit"] = str(API_LIMIT)

        if sport_path not in ("tennis"):
            d1 = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
            if league_path == "all":
                d2 = (date.today() + timedelta(days=5)).strftime("%Y%m%d")
            elif sport_path in ("baseball"):
                d2 = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
            else:
                d2 = (date.today() + timedelta(days=90)).strftime("%Y%m%d")
            url_parms["dates"] = f"{d1}-{d2}"

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
        if data is not None:
            _LOGGER.debug(
                "%s: Data returned for '%s' from %s",
                sensor_name,
                team_id,
                url,
            )
            try:
                num_events = len(data["events"])
            except:
                num_events = 0

        _LOGGER.debug(
            "%s: Num_events '%d' from %s",
            sensor_name,
            num_events,
            url,
        )
            
        # First fallback - without date constraint
        if num_events == 0:
            url_parms.pop("dates", None)
            url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/scoreboard"

            response = await self.async_call_espn_api(hass, url, url_parms, sensor_name, team_id)
            data = response["data"]
            url = response["url"]

            num_events = 0
            if data is not None:
                _LOGGER.debug(
                    "%s: Data returned for '%s' from %s",
                    sensor_name,
                    team_id,
                    url,
                )
                try:
                    num_events = len(data["events"])
                except:
                    num_events = 0

            _LOGGER.debug(
                "%s: Num_events '%d' from %s",
                sensor_name,
                num_events,
                url,
            )

        # Second fallback - without language
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
            data = response["data"]
            url = response["url"]
                    
        return {"data": data, "url": url}

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

        if file_override:
            data = await self._async_override_espn_api(sensor_name, team_id, base_url)
            return {"data": data, "url": url}


        headers = {"User-Agent": self._USER_AGENT, "Accept": "application/ld+json"}
        session = async_get_clientsession(hass)
        try:
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    try:
                        data = await r.json()
                    except json.JSONDecodeError as e:
                        _LOGGER.debug("%s: HockeyTech response not JSON: %s", sensor_name, e)
                        return {"data": None, "url": url}
                else:
                    _LOGGER.debug(
                        "%s: API returned status %s: %s", sensor_name, r.status, url
                    )
                    return {"data": None, "url": url}
        except (aiohttp.ClientError, TimeoutError) as e:
            _LOGGER.debug("%s: API call failed: %s", sensor_name, e)
            return {"data": None, "url": url}

        return {"data": data, "url": url}


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