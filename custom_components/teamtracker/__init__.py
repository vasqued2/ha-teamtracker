""" TeamTracker Team Status """
import asyncio
from datetime import date, datetime, timedelta, timezone
import json
import locale
import logging
import os
import re

import aiofiles
import arrow
from async_timeout import timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import ( # pylint: disable=reimported
    async_entries_for_config_entry,
    async_get,
    async_get as async_get_entity_registry,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
    DATA_PROVIDER_ESPN,
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
    SERVICE_NAME_CALL_API,
    URL_HEAD,
    URL_TAIL,
    USER_AGENT,
    VERSION,
)
from .event import async_process_event
from .hockeytech import (
    async_fetch_hockeytech_data,
    DATA_PROVIDER_HOCKEYTECH,
    RAPID_REFRESH_RATE_HOCKEYTECH,
)
from .utils import is_integer, async_call_espn_api, async_get_value, has_team

_LOGGER = logging.getLogger(__name__)


def _slug_to_name(slug: str) -> str:
    """Convert a season slug like '2025-26-english-premier-league' to 'English Premier League'."""
    if not slug:
        return ""
    body = re.sub(r"^\d{4}(-\d{2})?-", "", slug)
    if body == slug:
        return ""
    def _fmt_word(w):
        # Uppercase abbreviations (no vowels, e.g. "mls", "nfl"); title-case real words
        return w.upper() if w.isalpha() and not re.search(r"[aeiou]", w, re.I) else w.title()
    return " ".join(_fmt_word(w) for w in body.split("-"))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved entities."""


    async def get_entry_id_from_entity_id(hass: HomeAssistant, entity_id: str):
        """Retrieve entry_id from entity_id."""
        # Get the entity registry
        entity_registry = async_get_entity_registry(hass)

        # Find the entry associated with the given entity_id
        entry = entity_registry.async_get(entity_id)

        if entry:
            return entry.config_entry_id

        return None


    async def async_call_api_service(call):
        """Handle the service action call."""

        sport_path = str(call.data.get(CONF_SPORT_PATH, "football"))
        league_path = str(call.data.get(CONF_LEAGUE_PATH, "nfl"))
        team_id = str(call.data.get(CONF_TEAM_ID, "cle"))
        conference_id = call.data.get(CONF_CONFERENCE_ID, "")
        conference_id = "" if conference_id is None else str(conference_id)
        entity_ids = call.data.get("entity_id", "none")

        for entity_id in entity_ids:
            entry_id = await get_entry_id_from_entity_id(hass, entity_id)

            if entry_id: # Set up from UI, use entry_id as index
                sensor_coordinator = hass.data[DOMAIN][entry_id][COORDINATOR]
                sensor_coordinator.update_team_info(sport_path, league_path, team_id, conference_id)
                await sensor_coordinator.async_refresh()
            else: # Set up from YAML, use sensor_name (from entity_name) as index
                sensor_name = entity_id.split('.')[-1]
                if sensor_name in hass.data[DOMAIN] and COORDINATOR in hass.data[DOMAIN][sensor_name]:
                    sensor_coordinator = hass.data[DOMAIN][sensor_name][COORDINATOR]
                    sensor_coordinator.update_team_info(sport_path, league_path, team_id, conference_id)
                    await sensor_coordinator.async_refresh()
                else: # YAML had duplicate names so it doesn't match the entity_name
                    _LOGGER.info(
                        "%s: [service=call_api] No entry_id found (likely because of non-unique sensor names in YAML) for entity_id: %s",
                        sensor_name, 
                        entity_id,
                    )

    # Print startup message

    sensor_name = entry.data[CONF_NAME]

    _LOGGER.info(
        "%s: Setting up sensor from UI configuration using TeamTracker %s, if you have any issues please report them here: %s",
        sensor_name, 
        VERSION,
        ISSUE_URL,
    )

    # Initialize DOMAIN in hass.data if it doesn't exist
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        
    entry.async_on_unload(entry.add_update_listener(update_options_listener))

    if entry.unique_id is not None:
        _LOGGER.info(
            "%s: async_setup_entry() - entry.unique_id is not None: %s",
            sensor_name, 
            entry.unique_id,
        )
        hass.config_entries.async_update_entry(entry, unique_id=None)

        ent_reg = async_get(hass)
        for entity in async_entries_for_config_entry(ent_reg, entry.entry_id):
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=entry.entry_id)

    # Setup the data coordinator
    coordinator = TeamTrackerDataUpdateCoordinator(
        hass, entry.data, entry
    )

    # Fetch initial data so we have data when entities subscribe
#    await coordinator.async_refresh()

    # For UI, use entry_id as index
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
#
#  Register services for sensor
#
    hass.services.async_register(DOMAIN, SERVICE_NAME_CALL_API, async_call_api_service,)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    # Unload platforms
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
        
        # Only remove service if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_NAME_CALL_API)
            TeamTrackerDataUpdateCoordinator.data_cache.clear()
            TeamTrackerDataUpdateCoordinator.last_update.clear()
            TeamTrackerDataUpdateCoordinator.c_cache.clear()

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
            hass.config_entries.async_update_entry(entry, data=updated_config, version=3)

        _LOGGER.debug("%s: Migration to version %s complete", sensor_name, entry.version)

    return True


class TeamTrackerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TeamTracker data."""

    data_cache = {}
    last_update = {}
    c_cache = {}
    all_team_cache = {}  # {"{sport}:{league}:{team_id}": {next_game_date, league_map, expires}}

    def __init__(self, hass, config, entry: ConfigEntry=None):
        """Initialize."""
        self.name = config[CONF_NAME]
        self.api_url = ""
        self.league_id = config[CONF_LEAGUE_ID]
        self.league_path = config[CONF_LEAGUE_PATH]
        self.sport_path = config[CONF_SPORT_PATH]
        if self.sport_path.lower() == DATA_PROVIDER_HOCKEYTECH:
            self.data_provider = DATA_PROVIDER_HOCKEYTECH
        else:
            self.data_provider = DATA_PROVIDER_ESPN
        self.team_id = config[CONF_TEAM_ID]

        self.conference_id = ""
        if CONF_CONFERENCE_ID in config.keys():
            if len(config[CONF_CONFERENCE_ID]) > 0:
                self.conference_id = config[CONF_CONFERENCE_ID]

        self.config = config
        self.hass = hass
        self.entry = entry #None if setup from YAML

        super().__init__(hass, _LOGGER, name=self.name, update_interval=DEFAULT_REFRESH_RATE)
        _LOGGER.debug(
            "%s: Using default refresh rate (%s)", self.name, self.update_interval
        )


    #
    #  Return the language to use for the API
    #
    def get_lang(self):
        """Return language to use for API."""

        try:
            lang = self.hass.config.language
        except:
            lang, _ = locale.getlocale()
            lang = lang or "en_US"

        # Override language if is set in the configuration or options

        if CONF_API_LANGUAGE in self.config.keys():
            lang = self.config[CONF_API_LANGUAGE].lower()
        if self.entry and self.entry.options and CONF_API_LANGUAGE in self.entry.options and len(self.entry.options[CONF_API_LANGUAGE])>=2:
                lang = self.entry.options[CONF_API_LANGUAGE].lower()

        return lang


    #
    #  Set team info from service call
    #
    def update_team_info(self, sport_path, league_path, team_id, conference_id=""):
        """update team information when call_api service is called."""

        self.sport_path = sport_path
        self.league_path = league_path
        self.league_id = "XXX"
        self.team_id = team_id
        self.conference_id = conference_id

        lang = self.get_lang()
        key = sport_path + ":" + league_path + ":" + conference_id + ":" + lang
        if league_path == "all" and is_integer(self.team_id):
            key += ":" + team_id

        if key in TeamTrackerDataUpdateCoordinator.data_cache:
            del TeamTrackerDataUpdateCoordinator.data_cache[key]


    #
    #  async_get_team_schedule()
    #
    #    Calls the team info and schedule endpoints to discover the next game
    #    date and build an event_id → league name mapping (substring of season)
    #    Results are cached in all_team_cache until the next game date passes.
    #
    async def async_get_team_schedule(self, lang):
        """Fetch team schedule info for 'all' league date computation."""

        team_id = self.team_id
        sport_path = self.sport_path
        league_path = self.league_path
        sensor_name = self.name

        cache_key = f"{sport_path}:{league_path}:{team_id}"
        today = date.today()
        cached = TeamTrackerDataUpdateCoordinator.all_team_cache.get(cache_key)

        if cached is not None and today <= cached["expires"]:
            _LOGGER.debug("%s: all_team_cache hit for '%s'", sensor_name, team_id)
            return cached

        team_url = URL_HEAD + sport_path + "/" + league_path + "/teams/" + team_id

        league_map = {}
        next_events = []

        response = await async_call_espn_api(self.hass, team_url, None, sensor_name, team_id)
        team_data = response["data"]
        if team_data:
            next_events = team_data.get("team", {}).get("nextEvent", [])
            for ne in next_events:
                eid = ne.get("id")
                if not eid:
                    continue
                display = ne.get("season", {}).get("displayName") or _slug_to_name(
                    ne.get("season", {}).get("slug", "")
                )
                if display:
                    league_map[str(eid)] = display

        schedule_url = team_url + "/schedule"
        response = await async_call_espn_api(self.hass, schedule_url, None, sensor_name, team_id)
        sched_data = response["data"]
        if sched_data:
            for e in sched_data.get("events", []):
                eid = e.get("id")
                if not eid:
                    continue
                display = e.get("season", {}).get("displayName") or _slug_to_name(
                    e.get("season", {}).get("slug", "")
                )
                if display:
                    league_map[str(eid)] = display

        next_game_date = (
            date.fromisoformat(next_events[0]["date"][:10]) if next_events else None
        )

        result = {
            "next_game_date": next_game_date,
            "league_map": league_map,
            "expires": next_game_date or today,
        }
        TeamTrackerDataUpdateCoordinator.all_team_cache[cache_key] = result
        return result


    #
    #  DataUpdateCoordinator Call Tree
    #
    #  _async_update_data() - Top-level method called from HA to update sensor, controls refresh rate
    #    async_update_sport_data() - Determines to use cached data or API call (if exprired)
    #      async_call_sport_apis() - Calls appropriate set of APIs based on sport and league
    #        async_fetch_espn_data() - Gets data from ESPN APIs for specified league
    #          async_call_espn_api() - Mockable, overridable API call for ESPN APIs
    #        async_fetch_espn_all_leagues_data() - Gets data from ESPN APIs for all leagues in specified sport
    #          async_call_espn_api() - Mockable, overridable API call for ESPN APIs
    #        async_fetch_hockeytech_data() - Gets data from HockeyTech APIs for specified league
    #          async_call_hockeytech_api() - Mockable, overridable API call for HockeyTech APIs
    #      async_update_values() - Updates sensor values using data returned by API or in cache
    #        async_process_event() - Parses ESPN event structure and populates values for sensor
    #
    async def _async_update_data(self):
        """Top-level method called from HA to update sensor, controls refresh rate."""
        async with timeout(DEFAULT_TIMEOUT):
            try:
                data = await self.async_update_sport_data(self.config, self.hass)

                # update the interval based on flag
                if data["private_fast_refresh"]:
                    if self.update_interval != RAPID_REFRESH_RATE:
                        if self.data_provider == DATA_PROVIDER_HOCKEYTECH:
                            self.update_interval = RAPID_REFRESH_RATE_HOCKEYTECH
                        else:
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

#
#  async_update_sport_data()
#
    async def async_update_sport_data(self, config, hass) -> dict:
        """Determines to use cached data or API call (if exprired)"""

        sensor_name = self.name
        sport_path = self.sport_path
        league_path = self.league_path
        conference_id = self.conference_id

        lang = self.get_lang()

        # For "all" leagues, include team_id in cache key since each team
        # uses different narrow date windows for the scoreboard call.
        key = sport_path + ":" + league_path + ":" + conference_id + ":" + lang
        if league_path == "all" and is_integer(self.team_id):
            key += ":" + self.team_id

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
                values = await self.async_update_values(hass, data, lang)
                if values["api_message"]:
                    values["api_message"] = "Cached data: " + values["api_message"]
                else:
                    values["api_message"] = "Cached data"
                return values

        data = await self.async_call_sport_apis(hass, lang)
        values = await self.async_update_values(hass, data, lang)

        if data is not None:
            self.data_cache[key] = data
        self.last_update[key] = values["last_update"]

        if conference_id == "9999": # if conference_id is 9999, create results file for tests
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
    #  async_call_sport_apis()
    #    This is the API dispatcher, calls to new non-ESPN API's should be added here based on league_path.
    #      Response data should be formatted as an ESPN event.
    #
    async def async_call_sport_apis(self, hass, lang) -> dict:
        """Calls appropriate set of APIs based on sport and league."""

        league_path = self.league_path
        if self.data_provider == DATA_PROVIDER_HOCKEYTECH:
            response = await async_fetch_hockeytech_data(hass, league_path.upper(), self.name, lang)
        elif (league_path == "all") and is_integer(self.team_id):
            response = await self.async_fetch_espn_all_leagues_data(hass, lang)
        else:
            response = await self.async_fetch_espn_data(hass, lang)

        self.api_url = response["url"]
        return response["data"]


    #
    #  async_fetch_espn_data()
    #    Call ESPN API with using varying date ranges and parameters until events returned
    #      1. Call w/ sport specific date range
    #      2. Call w/o date range specfied (uses ESPN default behavior)
    #      3. Call w/o language parm (some sports not returned in some languages)
    #
    async def async_fetch_espn_data(self, hass, lang) -> dict:
        """Gets data from ESPN APIs for specified league."""

        sensor_name = self.name
        sport_path = self.sport_path
        league_path = self.league_path
        team_id = self.team_id.upper()

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
        if self.conference_id:
            url_parms["groups"] = self.conference_id
            if self.conference_id == "9999":
                file_override = True

        url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL

        response = await async_call_espn_api(hass, url, url_parms, sensor_name, team_id, file_override)
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

            url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL

            response = await async_call_espn_api(hass, url, url_parms, sensor_name, team_id)
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

            url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL
            _LOGGER.debug(
                "%s: Calling API without language for '%s' from %s",
                sensor_name,
                team_id,
                url,
            )

            response = await async_call_espn_api(hass, url, url_parms, sensor_name, team_id)
            data = response["data"]
            url = response["url"]
                    
        return {"data": data, "url": url}


    #
    #  async_fetch_espn_all_leagues_data()
    #    ESPN APIs returning all leagues quickly hit the API_LIMIT, so force use of tight date ranges
    #      1. Get the team schedule from ESPN and determine next upcoming game
    #      2. Call w/ date range up to upcoming game
    #      2. Call w/ date range around upcoming game
    #
    async def async_fetch_espn_all_leagues_data(self, hass, lang) -> dict:
        """Gets data from ESPN APIs for all leagues in specified sport."""

        sensor_name = self.name
        sport_path = self.sport_path
        league_path = self.league_path
        team_id = self.team_id.upper()

        # Get date of next game
        schedule_info = await self.async_get_team_schedule(lang)
        next_game_date = schedule_info.get("next_game_date") if schedule_info else None

        # Narrow window: cover recent results and upcoming game if within 7 days
        today_utc = datetime.now(timezone.utc).date()
        day_before_yesterday = today_utc - timedelta(days=2)

        d1 = day_before_yesterday.strftime("%Y%m%d")
        if next_game_date and next_game_date <= today_utc + timedelta(days=7):
            d2 = next_game_date.strftime("%Y%m%d")
        else:
            d2 = today_utc.strftime("%Y%m%d")

        _LOGGER.debug(
            "%s: All-league scoreboard call 1/1 dates=%s-%s (next_game=%s)",
            sensor_name, d1, d2,
            next_game_date.isoformat() if next_game_date else "unknown",
        )

        url_parms = {}
        url_parms["lang"] = lang[:2]
        url_parms["limit"] = str(API_LIMIT)
        url_parms["dates"] = f"{d1}-{d2}"

        url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL

        response = await async_call_espn_api(hass, url, url_parms, sensor_name, team_id)
        data = response["data"]
        url = response["url"]

        # If event for team not returned, narrow date range and try again
        if has_team(data, team_id) is False:
            if (next_game_date and next_game_date > today_utc):
                nd1 = (next_game_date - timedelta(days=1)).strftime("%Y%m%d")
                nd2 = next_game_date.strftime("%Y%m%d")
                if nd1 != d1 or nd2 != d2:  # avoid duplicate call
                    _LOGGER.debug(
                        "%s: All-league scoreboard call 2/2 dates=%s-%s (fallback to next game)",
                        sensor_name, nd1, nd2,
                    )

                    url_parms["dates"] = f"{nd1}-{nd2}"
                    url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL

                    response = await async_call_espn_api(hass, url, url_parms, sensor_name, team_id)
                    data = response["data"]
                    url = response["url"]

        return {"data": data, "url": url}


    #
    #  async_update_values()
    #
    async def async_update_values(self, hass, data, lang) -> dict:
        """Updates sensor values using data returned by API or in cache"""

        sensor_name = self.name
        league_id = self.league_id.upper()
        team_id = self.team_id.upper()

        # Populate base values that do not need API data
        values = {}
        values = await async_clear_values()
        if self.sport_path.lower() == "hockeytech":
            values["sport"] = "hockey"
        else:
            values["sport"] = self.sport_path
        values["sport_path"] = self.sport_path
        values["league"] = league_id
        values["league_path"] = self.league_path
        values["league_logo"] = DEFAULT_LOGO
        values["team_abbr"] = team_id
        values["state"] = "NOT_FOUND"
        values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
        values["private_fast_refresh"] = False
        values["api_url"] = self.api_url

        # If there was an error (i.e. 404) w/ the API call...
        if data is None:
            values["api_message"] = "API error, no data returned"
            _LOGGER.warning(
                "%s: API did not return any data for team '%s'", sensor_name, team_id
            )
            return values

        # When league_path is "all", parser needs league_map{} to do manual lookup
        league_map = {}
        if (self.league_path) == "all":
            cache_key = f"{self.sport_path}:{self.league_path}:{self.team_id}"
            team_cache = self.all_team_cache.get(cache_key)
            if team_cache:
                league_map = team_cache.get("league_map", {})

        values = await async_process_event(
            values,
            sensor_name,
            data,
            self.sport_path,
            league_id,
            DEFAULT_LOGO,
            team_id,
            league_map,
            lang,
        )

        # If NOT_FOUND, try to get abbr w/ another API to make message easier to read
        if (values["state"] == "NOT_FOUND" and is_integer(team_id)):
            url = (
                f"{URL_HEAD}/{self.sport_path}/{self.league_path}/teams/{team_id}"
            )
            response = await async_call_espn_api(hass, url, None, sensor_name, team_id)
            team_data = response["data"]
            if team_data:
                values["team_id"] = team_id
                values["team_abbr"] = await async_get_value(team_data, "team", "abbreviation", default=team_id)
        
        return values
