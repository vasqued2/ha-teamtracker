""" Home Assistant sensor processing """
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_API_LANGUAGE,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    COORDINATOR,
    DEFAULT_CONFERENCE_ID,
    DEFAULT_ICON,
    DEFAULT_LEAGUE,
    DEFAULT_NAME,
    DEFAULT_SPORT_PATH,
    DOMAIN,
    ISSUE_URL,
    NATIVE_LEAGUES,
    OVERRIDE_DICT,
    SPORT_ICON_MAP,
    VERSION,
)
from .coordinator import TeamTrackerCoordinator
from .utils import load_file_overrides

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LEAGUE_ID, default=DEFAULT_LEAGUE): vol.All(
            vol.Upper, vol.In([*NATIVE_LEAGUES.keys(), "XXX"])
        ),
        vol.Required(CONF_TEAM_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CONFERENCE_ID, default=DEFAULT_CONFERENCE_ID): cv.string,
        vol.Optional(CONF_API_LANGUAGE): cv.string,
        vol.Optional(CONF_SPORT_PATH): cv.string,
        vol.Optional(CONF_LEAGUE_PATH): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up the sensor from the YAML Configuration"""
    sensor_name = config[CONF_NAME]

    _LOGGER.info(
        "%s: Setting up sensor from YAML using TeamTracker %s, if you have any issues please report them here: %s",
        sensor_name, 
        VERSION,
        ISSUE_URL,
    )

    league_ids = [*NATIVE_LEAGUES.keys(), "XXX"]
    try:
        vol.In(league_ids)(config[CONF_LEAGUE_ID])
    except vol.Invalid:
        _LOGGER.warning("%s: `league_id` must be valid (one of %s)", sensor_name, league_ids)
        _LOGGER.error("%s: Support for invalid `league_id` in YAML was deprecated in v0.7.6.  Correct config prior to next upgrade.", sensor_name)
        return

    # Raise an exception if the league ID is XXX and the sport or league path is not
    # specified
    if config[CONF_LEAGUE_ID] == "XXX" and not (
        CONF_SPORT_PATH in config and CONF_LEAGUE_PATH in config
    ):
        error_msg = (
            "Must specify sport and league path for custom league (league_id = XXX)"
        )
        _LOGGER.warning("%s: %s", sensor_name, error_msg)
        return

    league_id = config[CONF_LEAGUE_ID].upper()
    # If the league ID is not in the map, it must be XXX and therefore we get the path
    # and league from the config
    config.update(
        NATIVE_LEAGUES.get(
            league_id,
            {
                k: v
                for k, v in config.items()
                if k in (CONF_SPORT_PATH, CONF_LEAGUE_PATH)
            },
        )
    )

    if DOMAIN not in hass.data.keys():
        hass.data.setdefault(DOMAIN, {})

    # Load the OVERRIDE_DICT if it doesn't exist
    if OVERRIDE_DICT not in hass.data[DOMAIN]:
        hass.data[DOMAIN][OVERRIDE_DICT] = None
        override_dict = await hass.async_add_executor_job(load_file_overrides, hass)
        if OVERRIDE_DICT not in hass.data[DOMAIN] or hass.data[DOMAIN][OVERRIDE_DICT] is None:
            hass.data[DOMAIN][OVERRIDE_DICT] = override_dict

    # Setup the data coordinator
    coordinator = TeamTrackerCoordinator(
        hass,
        config,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    # For YAML, use sensor name for index.  Assumes sensor_name = entity_name
    hass.data[DOMAIN][sensor_name] = {
        COORDINATOR: coordinator,
    }
    async_add_entities([TeamTrackerScoresSensor(hass, None, config)], True)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""

    sensor_name = entry.data[CONF_NAME]

    _LOGGER.info(
        "%s: Updating sensor from UI using TeamTracker %s, if you have any issues please report them here: %s",
        sensor_name, 
        VERSION,
        ISSUE_URL,
    )

    config = hass.data[DOMAIN][entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if entry.options:
        config.update(entry.options)

    async_add_entities([TeamTrackerScoresSensor(hass, entry, None)], True)


class TeamTrackerScoresSensor(CoordinatorEntity):
    """Representation of a Sensor."""
    _unrecorded_attributes = frozenset({"last_update"})

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, config: ConfigType) -> None:
        """Initialize the sensor."""

        if entry is not None:  # GUI setup, use entry_id as index
            entry_id = entry.entry_id
            sensor_coordinator = hass.data[DOMAIN][entry_id][COORDINATOR]
            super().__init__(sensor_coordinator)
            sport_path = entry.data.get(CONF_SPORT_PATH, DEFAULT_SPORT_PATH)
            sensor_name = entry.data[CONF_NAME]
            
        else:  # YAML setup, use sensor_name as index (assumes sensor_name = entity_id)
            sensor_name = config[CONF_NAME]
            entry_id = slugify(f"{config.get(CONF_TEAM_ID)}")
            sensor_coordinator = hass.data[DOMAIN][sensor_name][COORDINATOR]
            super().__init__(sensor_coordinator)
            self._yaml_coordinator = sensor_coordinator  # Store reference for cleanup

            try:
                sport_path = config[CONF_SPORT_PATH]
            except (KeyError, AttributeError):  # pylint: disable=broad-exception-caught
                sport_path = DEFAULT_SPORT_PATH

        if sport_path == DEFAULT_SPORT_PATH:
            _LOGGER.debug(
                "%s:  Initializing sensor values.  SPORT_PATH not set.",
                sensor_name,
            )

        icon = SPORT_ICON_MAP.get(sport_path, DEFAULT_ICON)
        if icon == DEFAULT_ICON:
            _LOGGER.debug(
                "%s:  Initializing sensor values.  Sport icon not found for sport '%s'",
                sensor_name,
                sport_path,
            )

        self._entry_id = entry_id
        self._name = sensor_name
        self._icon = icon

        self.coordinator = sensor_coordinator


    @property
    def unique_id(self) -> str:
        """
        Return a unique, Home Assistant friendly identifier for this entity.
        """
        return f"{slugify(self._name)}_{self._entry_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state message."""
        attrs: dict[str, Any] = {}

        if self.coordinator.data is None:
            return attrs
        attrs[ATTR_ATTRIBUTION] = self.coordinator.provider.ATTRIBUTION
        attrs.update(self.coordinator.data.to_dict_all_attr())
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is being removed."""
        # Only cleanup for YAML setup (entry is None)
        if hasattr(self, '_yaml_coordinator'):
            await self._yaml_coordinator.async_shutdown()
            _LOGGER.debug("%s: Cleaned up YAML coordinator", self._name)