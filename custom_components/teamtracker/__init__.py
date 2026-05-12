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
from typing import ClassVar

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
    DEFAULT_KICKOFF_IN,
    DEFAULT_LAST_UPDATE,
    DEFAULT_LEAGUE,
    DEFAULT_LOGO,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ISSUE_URL,
    NATIVE_LEAGUES,
    PLATFORMS,
    SERVICE_NAME_CALL_API,
    VERSION,
)
from .coordinator import TeamTrackerCoordinator
from .event import async_process_event
from .utils import is_integer, async_get_value, has_team

_LOGGER = logging.getLogger(__name__)


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
    coordinator = TeamTrackerCoordinator(
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
        domain_data = hass.data.get(DOMAIN, None)
        if domain_data:
            domain_data.pop(entry.entry_id)
        
        # Only remove service if this is the last entry
        if not domain_data:
            hass.services.async_remove(DOMAIN, SERVICE_NAME_CALL_API)
            TeamTrackerCoordinator.data_cache.clear()
            TeamTrackerCoordinator.all_team_cache.clear()

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
            updated_config.update(NATIVE_LEAGUES[league_id])

        if updated_config != entry.data:
            hass.config_entries.async_update_entry(entry, data=updated_config, version=3)

        _LOGGER.debug("%s: Migration to version %s complete", sensor_name, entry.version)

    return True