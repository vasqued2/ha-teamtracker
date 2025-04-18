""" Home Assistant sensor processing """
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.persistent_notification import async_create
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from . import TeamTrackerDataUpdateCoordinator
from .const import (
    ATTRIBUTION,
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
    LEAGUE_MAP,
    SPORT_ICON_MAP,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LEAGUE_ID, default=DEFAULT_LEAGUE): vol.All(
            vol.Upper, vol.In([*LEAGUE_MAP.keys(), "XXX"])
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

    league_ids = [*LEAGUE_MAP.keys(), "XXX"]
    try:
        vol.In(league_ids)(config[CONF_LEAGUE_ID])
    except vol.Invalid:
        _LOGGER.warning("%s: `league_id` must be valid (one of %s)", sensor_name, league_ids)
        _LOGGER.error("%s: Support for invalid `league_id` in YAML was deprecated in v0.7.6.  Correct config prior to next upgrade.", sensor_name)
        async_create(
            hass,
            f"{sensor_name} Error: `league_id` must be valid (one of {league_ids})",
            "Team Tracker",
            DOMAIN,
        )
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
        async_create(hass, f"{sensor_name} Error: {error_msg}", "Team Tracker", DOMAIN)
        return

    league_id = config[CONF_LEAGUE_ID].upper()
    # If the league ID is not in the map, it must be XXX and therefore we get the path
    # and league from the config
    config.update(
        LEAGUE_MAP.get(
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

    # Setup the data coordinator
    coordinator = TeamTrackerDataUpdateCoordinator(
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
            try:
                sport_path = config[CONF_SPORT_PATH]
            except:
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

        self.coordinator = sensor_coordinator
        self._entry_id = entry_id
        self._name = sensor_name
        self._icon = icon
        self._state = "PRE"

        self._sport = None
        self._sport_path = None
        self._league = None
        self._league_path = None
        self._league_logo = None
        self._season = None
        self._team_abbr = None
        self._opponent_abbr = None

        self._event_name = None
        self._event_url = None
        self._date = None
        self._kickoff_in = None
        self._series_summary = None
        self._venue = None
        self._location = None
        self._tv_network = None
        self._odds = None
        self._overunder = None

        self._team_name = None
        self._team_long_name = None
        self._team_id = None
        self._team_record = None
        self._team_rank = None
        self._team_conference_id = None
        self._team_homeaway = None
        self._team_logo = None
        self._team_url = None
        self._team_colors = None
        self._team_score = None
        self._team_win_probability = None
        self._team_winner = None
        self._team_timeouts = None

        self._opponent_name = None
        self._opponent_long_name = None
        self._opponent_id = None
        self._opponent_record = None
        self._opponent_rank = None
        self._opponent_conference_id = None
        self._opponent_homeaway = None
        self._opponent_logo = None
        self._opponent_url = None
        self._opponent_colors = None
        self._opponent_score = None
        self._opponent_win_probability = None
        self._opponent_winner = None
        self._opponent_timeouts = None

        self._quarter = None
        self._clock = None
        self._possession = None
        self._last_play = None
        self._down_distance_text = None

        self._outs = None
        self._balls = None
        self._strikes = None
        self._on_first = None
        self._on_second = None
        self._on_third = None

        self._team_shots_on_target = None
        self._team_total_shots = None
        self._opponent_shots_on_target = None
        self._opponent_total_shots = None

        self._team_sets_won = None
        self._opponent_sets_won = None

        self._last_update = None
        self._api_message = None
        self._api_url = None

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
    def state(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        if "state" in self.coordinator.data.keys():
            return self.coordinator.data["state"]

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state message."""
        attrs = {}

        if self.coordinator.data is None:
            return attrs

        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION

        attrs["sport"] = self.coordinator.data["sport"]
        attrs["sport_path"] = self.coordinator.data["sport_path"]
        attrs["league"] = self.coordinator.data["league"]
        attrs["league_path"] = self.coordinator.data["league_path"]
        attrs["league_logo"] = self.coordinator.data["league_logo"]
        attrs["season"] = self.coordinator.data["season"]
        attrs["team_abbr"] = self.coordinator.data["team_abbr"]
        attrs["opponent_abbr"] = self.coordinator.data["opponent_abbr"]

        attrs["event_name"] = self.coordinator.data["event_name"]
        attrs["event_url"] = self.coordinator.data["event_url"]
        attrs["date"] = self.coordinator.data["date"]
        attrs["kickoff_in"] = self.coordinator.data["kickoff_in"]
        attrs["series_summary"] = self.coordinator.data["series_summary"]
        attrs["venue"] = self.coordinator.data["venue"]
        attrs["location"] = self.coordinator.data["location"]
        attrs["tv_network"] = self.coordinator.data["tv_network"]
        attrs["odds"] = self.coordinator.data["odds"]
        attrs["overunder"] = self.coordinator.data["overunder"]

        attrs["team_name"] = self.coordinator.data["team_name"]
        attrs["team_long_name"] = self.coordinator.data["team_long_name"]
        attrs["team_id"] = self.coordinator.data["team_id"]
        attrs["team_record"] = self.coordinator.data["team_record"]
        attrs["team_rank"] = self.coordinator.data["team_rank"]
        attrs["team_conference_id"] = self.coordinator.data["team_conference_id"]
        attrs["team_homeaway"] = self.coordinator.data["team_homeaway"]
        attrs["team_logo"] = self.coordinator.data["team_logo"]
        attrs["team_url"] = self.coordinator.data["team_url"]
        attrs["team_colors"] = self.coordinator.data["team_colors"]
        #        attrs["team_colors_rbg"] = self.colors2rgb(self.coordinator.data["team_colors"])
        attrs["team_score"] = self.coordinator.data["team_score"]
        attrs["team_win_probability"] = self.coordinator.data["team_win_probability"]
        attrs["team_winner"] = self.coordinator.data["team_winner"]
        attrs["team_timeouts"] = self.coordinator.data["team_timeouts"]

        attrs["opponent_name"] = self.coordinator.data["opponent_name"]
        attrs["opponent_long_name"] = self.coordinator.data["opponent_long_name"]
        attrs["opponent_id"] = self.coordinator.data["opponent_id"]
        attrs["opponent_record"] = self.coordinator.data["opponent_record"]
        attrs["opponent_rank"] = self.coordinator.data["opponent_rank"]
        attrs["opponent_conference_id"] = self.coordinator.data["opponent_conference_id"]
        attrs["opponent_homeaway"] = self.coordinator.data["opponent_homeaway"]
        attrs["opponent_logo"] = self.coordinator.data["opponent_logo"]
        attrs["opponent_url"] = self.coordinator.data["opponent_url"]
        attrs["opponent_colors"] = self.coordinator.data["opponent_colors"]
        #        attrs["opponent_colors_rgb"] = self.colors2rgb(self.coordinator.data["opponent_colors"])
        attrs["opponent_score"] = self.coordinator.data["opponent_score"]
        attrs["opponent_win_probability"] = self.coordinator.data[
            "opponent_win_probability"
        ]
        attrs["opponent_winner"] = self.coordinator.data[
            "opponent_winner"
        ]
        attrs["opponent_timeouts"] = self.coordinator.data["opponent_timeouts"]

        attrs["quarter"] = self.coordinator.data["quarter"]
        attrs["clock"] = self.coordinator.data["clock"]
        attrs["possession"] = self.coordinator.data["possession"]
        attrs["last_play"] = self.coordinator.data["last_play"]
        attrs["down_distance_text"] = self.coordinator.data["down_distance_text"]

        attrs["outs"] = self.coordinator.data["outs"]
        attrs["balls"] = self.coordinator.data["balls"]
        attrs["strikes"] = self.coordinator.data["strikes"]
        attrs["on_first"] = self.coordinator.data["on_first"]
        attrs["on_second"] = self.coordinator.data["on_second"]
        attrs["on_third"] = self.coordinator.data["on_third"]

        attrs["team_shots_on_target"] = self.coordinator.data["team_shots_on_target"]
        attrs["team_total_shots"] = self.coordinator.data["team_total_shots"]
        attrs["opponent_shots_on_target"] = self.coordinator.data[
            "opponent_shots_on_target"
        ]
        attrs["opponent_total_shots"] = self.coordinator.data["opponent_total_shots"]

        attrs["team_sets_won"] = self.coordinator.data["team_sets_won"]
        attrs["opponent_sets_won"] = self.coordinator.data["opponent_sets_won"]

        attrs["last_update"] = self.coordinator.data["last_update"]
        attrs["api_message"] = self.coordinator.data["api_message"]
        attrs["api_url"] = self.coordinator.data["api_url"]

        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
