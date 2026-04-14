""" Miscellaneous Utilities """
import json
import aiofiles
import os
import logging

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


#
# Traverse json and return the value at the end of the chain of keys.
#    json - json to be traversed
#    *keys - list of keys to use to retrieve the value
#    default - default value to be returned if a key is missing
#
async def async_get_value(json_input, *keys, default=None):
    """Traverse the json using keys to return the associated value, or default if invalid keys"""

    j = json_input
    try:
        for k in keys:
            j = j[k]
        return j
    except:
        return default


def is_integer(val):
    """Check if a value is an integer"""

    try:
        int(val)
        return True
    except ValueError:
        return False


#
#  Call an ESPN API (or file use the appropriate file override) and get the data returned by it
#    This utility will eventually replace/wrap all API calls
#
async def async_call_espn_api2(hass, sensor_name, team_id, url, file_override=False) -> dict:
    """Call the specified ESPN API."""

    if file_override:
        data = await async_override_espn_api2(sensor_name, team_id, url)
    else:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/ld+json"}
        session = async_get_clientsession(hass)
        try:
            async with session.get(url, headers=headers) as r:
                _LOGGER.debug(
                    "%s: Calling API for '%s' from %s",
                    sensor_name,
                    team_id,
                    url,
                )
                if r.status == 200:
                    data = await r.json()
                else:
                    data = None
        except Exception as e: # pylint: disable=broad-exception-caught
            _LOGGER.debug("%s: API call failed: %s", sensor_name, e)
            data = None
        
    return data


#
#  Call an ESPN API (or file use the appropriate file override) and get the data returned by it
#    This utility will eventually replace/wrap all API calls
#
async def async_override_espn_api2(sensor_name, team_id, url) -> dict:
    """Read a json file to mock the ESPN API."""

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
    elif "/all/" in clear_url:
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
