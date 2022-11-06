import logging
import uuid

import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from . import TeamTrackerDataUpdateCoordinator

from .const import (
    ATTRIBUTION,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TIMEOUT,
    CONF_TEAM_ID,
    COORDINATOR,
    DEFAULT_CONFERENCE_ID,
    DEFAULT_ICON,
    DEFAULT_LEAGUE,
    DEFAULT_LEAGUE_PATH,
    DEFAULT_NAME,
    DEFAULT_SPORT_PATH,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LEAGUE_LIST,
    SPORT_LIST,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LEAGUE_ID, default=DEFAULT_LEAGUE): cv.string,
        vol.Required(CONF_TEAM_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,
        vol.Optional(CONF_CONFERENCE_ID, default=DEFAULT_CONFERENCE_ID): cv.string,
        vol.Optional(CONF_SPORT_PATH, default=DEFAULT_SPORT_PATH): cv.string,
        vol.Optional(CONF_LEAGUE_PATH, default=DEFAULT_LEAGUE_PATH): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Configuration from yaml"""

    _LOGGER.debug("%s: Setting up sensor from YAML", config[CONF_NAME])

    league_id = config[CONF_LEAGUE_ID].upper()
    for x in range(len(LEAGUE_LIST)):
        if LEAGUE_LIST[x][0] == league_id:
            config.update({CONF_SPORT_PATH: LEAGUE_LIST[x][1]})
            config.update({CONF_LEAGUE_PATH: LEAGUE_LIST[x][2]})

    if DOMAIN not in hass.data.keys():
        hass.data.setdefault(DOMAIN, {})
        config.entry_id = slugify(f"{config.get(CONF_TEAM_ID)}")
        config.data = config
    else:
        config.entry_id = slugify(f"{config.get(CONF_TEAM_ID)}")
        config.data = config

    # Setup the data coordinator
    coordinator = TeamTrackerDataUpdateCoordinator(
        hass,
        config,
        config[CONF_TIMEOUT],
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN][config.entry_id] = {
        COORDINATOR: coordinator,
    }
    async_add_entities([TeamTrackerScoresSensor(hass, config)], True)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup the sensor platform."""
    async_add_entities([TeamTrackerScoresSensor(hass, entry)], True)


class TeamTrackerScoresSensor(CoordinatorEntity):
    """Representation of a Sensor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(hass.data[DOMAIN][entry.entry_id][COORDINATOR])

        sport = entry.data[CONF_SPORT_PATH]
        icon = DEFAULT_ICON
        for x in range(len(SPORT_LIST)):
            if SPORT_LIST[x][0] == sport:
                icon = SPORT_LIST[x][1]
        if icon == DEFAULT_ICON:
            _LOGGER.debug("%s:  Setting up sensor from YAML.  Sport '%s' not found.", entry.data[CONF_NAME], sport)

        self.coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
        self._config = entry
        self._name = entry.data[CONF_NAME]
        self._icon = icon
        self._state = "PRE"

        self._sport = None
        self._league = None
        self._league_logo = None
        self._team_abbr = None
        self._opponent_abbr = None

        self._event_name = None
        self._date = None
        self._kickoff_in = None
        self._venue = None
        self._location = None
        self._tv_network = None
        self._odds = None
        self._overunder = None

        self._team_name = None
        self._team_id = None
        self._team_record = None
        self._team_rank = None
        self._team_homeaway = None
        self._team_logo = None
        self._team_colors = None
        self._team_score = None
        self._team_win_probability = None
        self._team_timeouts = None

        self._opponent_name = None
        self._opponent_id = None
        self._opponent_record = None
        self._opponent_rank = None
        self._opponent_homeaway = None
        self._opponent_logo = None
        self._opponent_colors = None
        self._opponent_score = None
        self._opponent_win_probability = None
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


    @property
    def unique_id(self):
        """
        Return a unique, Home Assistant friendly identifier for this entity.
        """
        return f"{slugify(self._name)}_{self._config.entry_id}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        elif "state" in self.coordinator.data.keys():
            return self.coordinator.data["state"]
        else:
            return None

    @property
    def extra_state_attributes(self):
        """Return the state message."""
        attrs = {}

        if self.coordinator.data is None:
            return attrs

        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION

        attrs["sport"] = self.coordinator.data["sport"]
        attrs["league"] = self.coordinator.data["league"]
        attrs["league_logo"] = self.coordinator.data["league_logo"]
        attrs["team_abbr"] = self.coordinator.data["team_abbr"]
        attrs["opponent_abbr"] = self.coordinator.data["opponent_abbr"]

        attrs["event_name"] = self.coordinator.data["event_name"]
        attrs["date"] = self.coordinator.data["date"]
        attrs["kickoff_in"] = self.coordinator.data["kickoff_in"]
        attrs["venue"] = self.coordinator.data["venue"]
        attrs["location"] = self.coordinator.data["location"]
        attrs["tv_network"] = self.coordinator.data["tv_network"]
        attrs["odds"] = self.coordinator.data["odds"]
        attrs["overunder"] = self.coordinator.data["overunder"]

        attrs["team_name"] = self.coordinator.data["team_name"]
        attrs["team_id"] = self.coordinator.data["team_id"]
        attrs["team_record"] = self.coordinator.data["team_record"]
        attrs["team_rank"] = self.coordinator.data["team_rank"]
        attrs["team_homeaway"] = self.coordinator.data["team_homeaway"]
        attrs["team_logo"] = self.coordinator.data["team_logo"]
        attrs["team_colors"] = self.coordinator.data["team_colors"]
#        attrs["team_colors_rbg"] = self.colors2rgb(self.coordinator.data["team_colors"])
        attrs["team_score"] = self.coordinator.data["team_score"]
        attrs["team_win_probability"] = self.coordinator.data["team_win_probability"]
        attrs["team_timeouts"] = self.coordinator.data["team_timeouts"]

        attrs["opponent_name"] = self.coordinator.data["opponent_name"]
        attrs["opponent_id"] = self.coordinator.data["opponent_id"]
        attrs["opponent_record"] = self.coordinator.data["opponent_record"]
        attrs["opponent_rank"] = self.coordinator.data["opponent_rank"]
        attrs["opponent_homeaway"] = self.coordinator.data["opponent_homeaway"]
        attrs["opponent_logo"] = self.coordinator.data["opponent_logo"]
        attrs["opponent_colors"] = self.coordinator.data["opponent_colors"]
#        attrs["opponent_colors_rgb"] = self.colors2rgb(self.coordinator.data["opponent_colors"])
        attrs["opponent_score"] = self.coordinator.data["opponent_score"]
        attrs["opponent_win_probability"] = self.coordinator.data["opponent_win_probability"]
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
        attrs["opponent_shots_on_target"] = self.coordinator.data["opponent_shots_on_target"]
        attrs["opponent_total_shots"] = self.coordinator.data["opponent_total_shots"]

        attrs["team_sets_won"] = self.coordinator.data["team_sets_won"]
        attrs["opponent_sets_won"] = self.coordinator.data["opponent_sets_won"]

        attrs["last_update"] = self.coordinator.data["last_update"]
        attrs["api_message"] = self.coordinator.data["api_message"]

        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success


    def colors2rgb(self, colors) -> tuple:
        if colors is None:
            return None
        color_list = []
        color_list.append(list(self.hex_to_rgb(colors[0])))
        color_list.append(list(self.hex_to_rgb(colors[1])))
        return color_list

    def hex_to_rgb(self, hexa) -> tuple:
        hexa = hexa.lstrip("#")
        return tuple(int(hexa[i : i + 2], 16) for i in (0, 2, 4))