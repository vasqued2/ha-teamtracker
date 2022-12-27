""" TeamTracker Team Status """
import asyncio
import logging
from datetime import date, datetime, timedelta
import arrow
import json
import codecs
import locale
import os

import aiohttp
import aiofiles
from async_timeout import timeout
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .clear_values import async_clear_values
from .event import async_process_event
from .set_values import (
    async_set_values,
    async_set_in_values,
)
from .set_baseball import async_set_baseball_values
from .set_hockey import async_set_hockey_values
from .set_soccer import async_set_soccer_values
from .set_volleyball import async_set_volleyball_values
from .utils import async_get_value

from .const import (
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TIMEOUT,
    CONF_TEAM_ID,
    COORDINATOR,
    DEFAULT_CONFERENCE_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_LEAGUE,
    DEFAULT_LOGO,
    DEFAULT_LEAGUE_PATH,
    DEFAULT_PROB,
    DEFAULT_SPORT_PATH,
    DOMAIN,
    ISSUE_URL,
    LEAGUE_LIST,
    PLATFORMS,
    SPORT_LIST,
    URL_HEAD,
    URL_TAIL,
    USER_AGENT,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)
#team_prob = {}
#oppo_prob = {}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    # Print startup message
    _LOGGER.info("TeamTracker version %s is starting, if you have any issues please report them here: %s", VERSION, ISSUE_URL,)
    hass.data.setdefault(DOMAIN, {})

#
#  No support for an Options flow at this time.  Uncomment line below if ever added.
#    entry.add_update_listener(update_listener)

    if entry.unique_id is not None:
        hass.config_entries.async_update_entry(entry, unique_id=None)

        ent_reg = async_get(hass)
        for entity in async_entries_for_config_entry(ent_reg, entry.entry_id):
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=entry.entry_id)

    # Setup the data coordinator
    coordinator = TeamTrackerDataUpdateCoordinator(
        hass,
        entry.data,
        entry.data.get(CONF_TIMEOUT)
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    _LOGGER.debug("Attempting to unload entities from the %s integration", DOMAIN)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        _LOGGER.debug("Successfully removed entities from the %s integration", DOMAIN)
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok

#
#  Only needed if Options Flow is added
#
#async def update_listener(hass, entry):
#    """Update listener."""
#    entry.data = entry.options
#    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
#    hass.async_add_job(hass.config_entries.async_forward_entry_setup(entry, "sensor"))


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry."""
    version = config_entry.version

    # 1-> 2->3: Migration format
    # Add CONF_TIMEOUT, CONF_LEAGUE_ID, CONF_SPORT_PATH, and CONF_LEAGUE_PATH if not already populated
    if version < 3:
        _LOGGER.debug("Migrating from version %s", version)
        updated_config = config_entry.data.copy()

        if CONF_TIMEOUT not in updated_config.keys():
            updated_config[CONF_TIMEOUT] = DEFAULT_TIMEOUT
        if CONF_LEAGUE_ID not in updated_config.keys():
            updated_config[CONF_LEAGUE_ID] = DEFAULT_LEAGUE
        if (CONF_SPORT_PATH not in updated_config.keys()) or (CONF_LEAGUE_PATH not in updated_config.keys()):
            league_id = updated_config[CONF_LEAGUE_ID].upper()
            updated_config[CONF_SPORT_PATH] = DEFAULT_SPORT_PATH
            updated_config[CONF_LEAGUE_PATH] = DEFAULT_LEAGUE_PATH
            for x in range(len(LEAGUE_LIST)):
                if LEAGUE_LIST[x][0] == league_id:
                    updated_config[CONF_SPORT_PATH] = LEAGUE_LIST[x][1]
                    updated_config[CONF_LEAGUE_PATH] = LEAGUE_LIST[x][2]

        if updated_config != config_entry.data:
            hass.config_entries.async_update_entry(config_entry, data=updated_config)

        config_entry.version = 3
        _LOGGER.debug("Migration to version %s complete", config_entry.version)

    return True


class TeamTrackerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TeamTracker data."""

    def __init__(self, hass, config, the_timeout: int):
        """Initialize."""
        self.interval = timedelta(minutes=10)
        self.name = config[CONF_NAME]
        self.timeout = the_timeout
        self.config = config
        self.hass = hass

        _LOGGER.debug("%s: Data will be updated every %s minutes", self.name, self.interval)

        super().__init__(hass, _LOGGER, name=self.name, update_interval=self.interval)


    async def _async_update_data(self):
        """Fetch data"""
        async with timeout(self.timeout):
            try:
                data = await update_game(self.config, self.hass)
                # update the interval based on flag
                if data["private_fast_refresh"] == True:
                    self.update_interval = timedelta(seconds=5)
                else:
                    self.update_interval = timedelta(minutes=10)
            except Exception as error:
                raise UpdateFailed(error) from error
            return data
        

async def update_game(config, hass) -> dict:
    """Fetch new state data for the sensor.
    This is the only method that should fetch new data for Home Assistant.
    """

    data = await async_get_state(config, hass)
    return data


async def async_get_state(config, hass) -> dict:
    """Query API for status."""

    values = {}
    prev_values = {}
    headers = {"User-Agent": USER_AGENT, "Accept": "application/ld+json"}
    sensor_name = config[CONF_NAME]

    data = None
    file_override = False
    first_date = (date.today() - timedelta(days = 1)).strftime("%Y-%m-%dT%H:%MZ")
    last_date =  (date.today() + timedelta(days = 5)).strftime("%Y-%m-%dT%H:%MZ")

#
#  Get the language based on the locale
#    Then override it if there is a value in frontend_storage for the selected language
#      (it usually takes about a minute after reboot for frontend_storage to be populated)
#

    lang, enc = locale.getlocale()
    lang = lang or "en_US"
    enc = enc or "UTF-8"

#    for t in hass.data["frontend_storage"]:
#        for key, value in t.items():
#            if "dict" in str(type(value)):
#                try:
#                    lang = value["language"]["language"]
#                except:
#                    lang = lang 

    league_id = config[CONF_LEAGUE_ID].upper()
    sport_path = config[CONF_SPORT_PATH]
    league_path = config[CONF_LEAGUE_PATH]
    url_parms = "?lang=" + lang[:2]

    _LOGGER.debug("%s: league %s, sport %s, team %s, conf %s", sensor_name, league_id, sport_path, config[CONF_TEAM_ID], config[CONF_CONFERENCE_ID])


    d1 = (date.today() - timedelta(days = 1)).strftime("%Y%m%d")
    d2 = (date.today() + timedelta(days = 5)).strftime("%Y%m%d")
    url_parms = url_parms + "&dates=" + d1 + "-" + d2

    if CONF_CONFERENCE_ID in config.keys():
            if (len(config[CONF_CONFERENCE_ID]) > 0):
                url_parms = url_parms + "&groups=" + config[CONF_CONFERENCE_ID]
                if (config[CONF_CONFERENCE_ID] == '9999'):
                    file_override = True
    team_id = config[CONF_TEAM_ID].upper()
    url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL + url_parms
    
    if (file_override):
        _LOGGER.debug("%s: Overriding API for '%s' cwd='%s'", sensor_name, team_id, os. getcwd())
        async with aiofiles.open('custom_components/tests/tt/all.json', mode='r') as f:
            contents = await f.read()
        data = json.loads(contents)
        if data is None:
            _LOGGER.debug("%s: /share/tt/test.json does not exist.  Trying test files. '%s'", sensor_name, team_id)
            async with aiofiles.open('custom_components/tests/tt/all.json', mode='r') as f:
                contents = await f.read()
            data = json.loads(contents)
    else:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as r:
                _LOGGER.debug("%s: Getting state for '%s' from %s", sensor_name, team_id, url)
                if r.status == 200:
                    data = await r.json()

        num_events = 0
        if data is not None:
            try:
                num_events = len(data["events"])
            except:
                num_events = 0

        if num_events == 0:
            url_parms = "?lang=" + lang[:2]
            if CONF_CONFERENCE_ID in config.keys():
                    if (len(config[CONF_CONFERENCE_ID]) > 0):
                        url_parms = url_parms + "&groups=" + config[CONF_CONFERENCE_ID]
                        if (config[CONF_CONFERENCE_ID] == '9999'):
                            file_override = True
            url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL + url_parms

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as r:
                    _LOGGER.debug("%s: Getting state without date constraint for '%s' from %s", sensor_name, team_id, url)
                    if r.status == 200:
                        data = await r.json()

    team_id = config[CONF_TEAM_ID].upper()

    search_key = team_id
    sport = sport_path
    found_competitor = False

    values = await async_clear_values()
    values["sport"] = sport_path
    values["league"] = league_id
    values["league_logo"] = DEFAULT_LOGO
    values["team_abbr"] = team_id
    values["state"] = "NOT_FOUND"
    values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
    values["private_fast_refresh"] = False

    if data is None:
        values["api_message"] = "API error, no data returned"
        _LOGGER.warn("%s: API did not return any data for team '%s':  %s", sensor_name, team_id, url)
        return values

#    if sport_path in ["football", "golf", "mma", "racing", "tennis"]:
    if True:
        values = await async_process_event(values, sensor_name, data, sport_path, league_id, DEFAULT_LOGO, team_id, lang, url)
        return values

    found_team = False
    if data is not None:
        values["league_logo"] = await async_get_value(data, "leagues", 0, "logos", 0, "href",
            default=DEFAULT_LOGO)

        for event in data["events"]:
            #_LOGGER.debug("%s: Looking at this event: %s" sensor_name, event)
            try:
                sn = event["shortName"]
            except:
                sn = ""
                _LOGGER.debug("%s: This is an ill-formed event, it does not have a short name: %s", sensor_name, event)
            try:
                t0 = event["competitions"][0]["competitors"][0]["team"]["abbreviation"]
            except:
                t0 = ""
            try:
                t1 = event["competitions"][0]["competitors"][1]["team"]["abbreviation"]
            except:
                t1 = ""
            try:
                if (last_date < event["date"]):
                    last_date = event["date"]
            except:
                last_date = last_date
            try:
                if (event["date"] < first_date):
                    first_date = event["date"]
            except:
                first_date = first_date

            if sn.startswith(team_id + ' ') or sn.endswith(' ' + team_id) or t0 == team_id or t1 == team_id:
                found_team = True
                prev_values = values.copy()

                _LOGGER.debug("%s: Found event for %s; parsing data.", sensor_name, team_id)

                if t0 == team_id:
                    team_index = 0
                elif t1 == team_id:
                    team_index = 1
                else:
                    if sn.startswith(team_id + ' '): # Lazy, but assumes first team in short_name is always team_index 1.
                        team_index = 1
                        values["api_message"] = "Unmatched team_id '" + team_id + "' (lang=en), using team_abbr '" + t1 + "' (lang=" + lang + ")"
                        _LOGGER.warn("%s: Sensor created with team_id '%s' (lang=en).  Using team_abbr '%s' (lang=%s).  Recreate sensor using team_abbr for best performance.", sensor_name, team_id, t1, lang)
                    else:
                        team_index = 0
                        values["api_message"] = "Unmatched team_id '" + team_id + "' (lang=en), using team_abbr '" + t0 + "' (lang=" + lang + ")"
                        _LOGGER.warn("%s: Sensor created with team_id '%s' (lang=en).  Using team_abbr '%s' (lang=%s).  Recreate sensor using team_abbr for best performance.", sensor_name, team_id, t0, lang)

                oppo_index = abs((team_index-1))

                rc = await async_set_values(values, event, 0, team_index, lang, sensor_name)
                _LOGGER.debug("%s: post async_set_universal_values() %s", sensor_name, values)

                if values["state"] == "IN":
                    break

                if ((values["state"] == "PRE") and (abs((arrow.get(values["date"])-arrow.now()).total_seconds()) < 1200)):
                    break

                if prev_values["state"] == "POST":
                    if values["state"] == "PRE": # Use POST if PRE is more than 18 hours in future
                        if (abs((arrow.get(values["date"])-arrow.now()).total_seconds()) > 64800):
                            values = prev_values
                    elif values["state"] == "POST": # use POST w/ latest date
                        if (arrow.get(prev_values["date"]) > arrow.get(values["date"])):
                            values = prev_values
                if prev_values["state"] == "PRE":
                    if values["state"] == "PRE":  # use PRE w/ earliest date
                        if (arrow.get(prev_values["date"]) < arrow.get(values["date"])):
                            values = prev_values
                    elif values["state"] == "POST": # Use PRE if less than 18 hours in future
                        if (abs((arrow.get(prev_values["date"])-arrow.now()).total_seconds()) < 64800):
                            values = prev_values

        # Never found the team. Either a bye or a post-season condition
        if not found_team:
            _LOGGER.debug("%s: Did not find a game for team '%s'. Checking if it's a bye week.", sensor_name, team_id)
            found_bye = False
            try: # look for byes in regular season
                for bye_team in data["week"]["teamsOnBye"]:
                    if team_id.lower() == bye_team["abbreviation"].lower():
                        _LOGGER.debug("%s: Bye week confirmed.", sensor_name)
                        found_bye = True
                        values["team_abbr"] = bye_team["abbreviation"]
                        values["team_name"] = bye_team["shortDisplayName"]
                        values["team_logo"] = bye_team["logo"]
                        values["state"] = 'BYE'
                        values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
                if found_bye == False:
                    values["api_message"] = "No game scheduled for '" + team_id + "' between " + first_date + " and " + last_date
                    _LOGGER.debug("%s: Competitor information '%s' not returned by API: %s", sensor_name, team_id, url)
                    values["state"] = 'NOT_FOUND'
                    values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
            except:
                values["api_message"] = "No game scheduled for '" + team_id + "' between " + first_date + " and " + last_date
                _LOGGER.debug("$s: Competitor information '%s' not returned by API: %s", sensor_name, team_id, url)
                values["state"] = 'NOT_FOUND'
                values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
        if values["state"] == 'PRE' and (abs((arrow.get(values["date"])-arrow.now()).total_seconds()) < 1200):
            _LOGGER.debug("%s: Event is within 20 minutes, setting refresh rate to 5 seconds.", sensor_name)
            values["private_fast_refresh"] = True
        elif values["state"] == 'IN':
            _LOGGER.debug("%s: Event in progress, setting refresh rate to 5 seconds.", sensor_name)
            values["private_fast_refresh"] = True
        elif values["state"] in ['POST', 'BYE']: 
            _LOGGER.debug("%s: Event is over, setting refresh back to 10 minutes.", sensor_name)
            values["private_fast_refresh"] = False

        
    return values