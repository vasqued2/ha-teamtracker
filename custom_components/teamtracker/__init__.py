""" TeamTracker Team Status """
import asyncio
from datetime import date, datetime, timedelta, timezone
import json
import locale
import logging
import os

import aiofiles
import aiohttp
import arrow
from async_timeout import timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .clear_values import async_clear_values
from .const import (
    API_LIMIT,
    CONF_API_LANGUAGE,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    COORDINATOR,
    DEFAULT_KICKOFF_IN,
    DEFAULT_LAST_UPDATE,
    DEFAULT_LEAGUE,
    DEFAULT_LOGO,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ISSUE_URL,
    LEAGUE_MAP,
    PLATFORMS,
    DEFAULT_REFRESH_RATE,
    RAPID_REFRESH_RATE,
    URL_HEAD,
    URL_TAIL,
    USER_AGENT,
    VERSION,
)
from .event import async_process_event

_LOGGER = logging.getLogger(__name__)
# team_prob = {}
# oppo_prob = {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    # Print startup message

    sensor_name = entry.data[CONF_NAME]

    _LOGGER.info(
        "%s: Setting up sensor from UI configuration using TeamTracker %s, if you have any issues please report them here: %s",
        sensor_name, 
        VERSION,
        ISSUE_URL,
    )
    hass.data.setdefault(DOMAIN, {})

    entry.async_on_unload(entry.add_update_listener(update_options_listener))

    if entry.unique_id is not None:
        hass.config_entries.async_update_entry(entry, unique_id=None)

        ent_reg = async_get(hass)
        for entity in async_entries_for_config_entry(ent_reg, entry.entry_id):
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=entry.entry_id)

    # Setup the data coordinator
    coordinator = TeamTrackerDataUpdateCoordinator(
        hass, entry.data, entry
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


#
#  Only needed if Options Flow is added
#
async def update_options_listener(hass, entry):
    """Update listener."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    sensor_name = entry.data[CONF_NAME]
    version = entry.version

    # 1-> 2->3: Migration format
    # Add CONF_LEAGUE_ID, CONF_SPORT_PATH, and CONF_LEAGUE_PATH if not already populated
    if version < 3:
        _LOGGER.debug("%s: Migrating from version %s", sensor_name, version)
        updated_config = entry.data.copy()

        if CONF_LEAGUE_ID not in updated_config.keys():
            updated_config[CONF_LEAGUE_ID] = DEFAULT_LEAGUE
        if (CONF_SPORT_PATH not in updated_config.keys()) or (
            CONF_LEAGUE_PATH not in updated_config.keys()
        ):
            league_id = updated_config[CONF_LEAGUE_ID].upper()
            updated_config.update(LEAGUE_MAP[league_id])

        if updated_config != entry.data:
            hass.config_entries.async_update_entry(entry, data=updated_config)

        entry.version = 3
        _LOGGER.debug("%s: Migration to version %s complete", sensor_name, entry.version)

    return True


class TeamTrackerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TeamTracker data."""

    data_cache = {}
    last_update = {}
    c_cache = {}

    def __init__(self, hass, config, entry: ConfigEntry=None):
        """Initialize."""
        self.name = config[CONF_NAME]
        self.config = config
        self.hass = hass
        self.entry = entry #None if setup from YAML

        super().__init__(hass, _LOGGER, name=self.name, update_interval=DEFAULT_REFRESH_RATE)
        _LOGGER.debug(
            "%s: Using default refresh rate (%s)", self.name, self.update_interval
        )



    #
    #  Top-level method called from HA to update data for all teamtracker sensors
    #
    async def _async_update_data(self):
        """Update data."""
        async with timeout(DEFAULT_TIMEOUT):
            try:
                data = await self.async_update_game_data(self.config, self.hass)

                # update the interval based on flag
                if data["private_fast_refresh"]:
                    if self.update_interval != RAPID_REFRESH_RATE:
                        self.update_interval = RAPID_REFRESH_RATE
                        _LOGGER.debug(
                            "%s: Switching to rapid refresh rate (%s)", self.name, self.update_interval
                        )
                else:
                    if self.update_interval != DEFAULT_REFRESH_RATE:
                        self.update_interval = DEFAULT_REFRESH_RATE
                        _LOGGER.debug(
                            "%s: Switching to default refresh rate (%s)", self.name, self.update_interval
                        )
            except Exception as error:
                _LOGGER.debug("%s: Error updating data: %s", self.name, error)
                _LOGGER.debug("%s: Error type: %s", self.name, type(error).__name__)
                _LOGGER.debug("%s: Additional information: %s", self.name, str(error))
                raise UpdateFailed(error) from error
            return data

    async def async_update_game_data(self, config, hass) -> dict:
        """Update game data from data_cache or the API (if expired)"""

        sensor_name = config[CONF_NAME]
        sport_path = config[CONF_SPORT_PATH]
        league_path = config[CONF_LEAGUE_PATH]
        conference_id = config[CONF_CONFERENCE_ID]

        try:
            lang = hass.config.language
        except:
            lang, _ = locale.getlocale()
            lang = lang or "en_US"

        # Override language if is set in the configuration or options

        if CONF_API_LANGUAGE in config.keys():
            lang = config[CONF_API_LANGUAGE].lower()
        if self.entry and self.entry.options and CONF_API_LANGUAGE in self.entry.options and len(self.entry.options[CONF_API_LANGUAGE])>=2:
                lang = self.entry.options[CONF_API_LANGUAGE].lower()

        key = sport_path + ":" + league_path + ":" + conference_id + ":" + lang

        #
        #  Use cache if not expired
        #
        if key in self.data_cache:
            expiration = (
                datetime.fromisoformat(self.last_update[key]) + self.update_interval
            )
            now = datetime.now(timezone.utc)

            if now < expiration:
                data = self.data_cache[key]
                values = await self.async_update_values(config, hass, data, lang)
                if values["api_message"]:
                    values["api_message"] = "Cached data: " + values["api_message"]
                else:
                    values["api_message"] = "Cached data"
                return values

        #
        #  Call the API
        #  Get the language based on the locale
        #    Then override it if there is a value in frontend_storage for the selected language
        #      (it usually takes about a minute after reboot for frontend_storage to be populated)
        #

        data, file_override = await self.async_call_api(config, hass, lang)
        values = await self.async_update_values(config, hass, data, lang)
        self.data_cache[key] = data
        self.last_update[key] = values["last_update"]

        if file_override:
            path = "/share/tt/results/" + sensor_name + ".json"
            if not os.path.exists(path):
                _LOGGER.debug("%s: Creating results file '%s'", sensor_name, path)
                values[
                    "last_update"
                ] = DEFAULT_LAST_UPDATE  # set to fixed time for compares
                values["kickoff_in"] = DEFAULT_KICKOFF_IN
                try:
                    with open(path, "w", encoding="utf-8") as convert_file:
                        convert_file.write(json.dumps(values, indent=4))
                except:
                    _LOGGER.debug(
                        "%s: Error creating results file '%s'", sensor_name, path
                    )
        return values

    #
    #  Call the API (or file override) and get the data returned by it
    #
    async def async_call_api(self, config, hass, lang) -> dict:
        """Query API for status."""

        headers = {"User-Agent": USER_AGENT, "Accept": "application/ld+json"}
        sensor_name = config[CONF_NAME]

        data = None
        file_override = False

        sport_path = config[CONF_SPORT_PATH]
        league_path = config[CONF_LEAGUE_PATH]

        url_parms = "?lang=" + lang[:2] + "&limit=" + str(API_LIMIT)

        if sport_path not in ("tennis", "baseball"):
            d1 = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
            d2 = (date.today() + timedelta(days=5)).strftime("%Y%m%d")
            url_parms = url_parms + "&dates=" + d1 + "-" + d2

        if CONF_CONFERENCE_ID in config.keys():
            if len(config[CONF_CONFERENCE_ID]) > 0:
                url_parms = url_parms + "&groups=" + config[CONF_CONFERENCE_ID]
                if config[CONF_CONFERENCE_ID] == "9999":
                    file_override = True
        team_id = config[CONF_TEAM_ID].upper()
        url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL + url_parms

        if file_override:
            _LOGGER.debug("%s: Overriding API for '%s'", sensor_name, team_id)
            file_path = "/share/tt/test.json"
            if not os.path.exists(file_path):
                file_path = "tests/tt/all.json"
            async with aiofiles.open(file_path, mode="r") as f:
                contents = await f.read()
            data = json.loads(contents)
        else:
            async with aiohttp.ClientSession() as session:
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
                except:
                    data = None

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
            if num_events == 0:
                url_parms = "?lang=" + lang[:2]
                if CONF_CONFERENCE_ID in config.keys():
                    if len(config[CONF_CONFERENCE_ID]) > 0:
                        url_parms = url_parms + "&groups=" + config[CONF_CONFERENCE_ID]
                        if config[CONF_CONFERENCE_ID] == "9999":
                            file_override = True

                url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL + url_parms

                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(url, headers=headers) as r:
                            _LOGGER.debug(
                                "%s: Calling API without date constraint for '%s' from %s",
                                sensor_name,
                                team_id,
                                url,
                            )
                            if r.status == 200:
                                data = await r.json()
                    except:
                        data = None

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

            if num_events == 0:
                url_parms = ""
                if CONF_CONFERENCE_ID in config.keys():
                    if len(config[CONF_CONFERENCE_ID]) > 0:
                        url_parms = url_parms + "?groups=" + config[CONF_CONFERENCE_ID]
                        if config[CONF_CONFERENCE_ID] == "9999":
                            file_override = True

                url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL + url_parms

                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(url, headers=headers) as r:
                            _LOGGER.debug(
                                "%s: Calling API without language for '%s' from %s",
                                sensor_name,
                                team_id,
                                url,
                            )
                            if r.status == 200:
                                data = await r.json()
                    except:
                        data = None

        return data, file_override

    async def async_update_values(self, config, hass, data, lang) -> dict:
        """Return values based on the data passed into method"""

        values = {}
        sensor_name = config[CONF_NAME]

        league_id = config[CONF_LEAGUE_ID].upper()
        sport_path = config[CONF_SPORT_PATH]

        team_id = config[CONF_TEAM_ID].upper()

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
            _LOGGER.warning(
                "%s: API did not return any data for team '%s'", sensor_name, team_id
            )
            return values

        values = await async_process_event(
            values,
            sensor_name,
            data,
            sport_path,
            league_id,
            DEFAULT_LOGO,
            team_id,
            lang,
        )

        return values
