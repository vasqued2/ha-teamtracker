"""Adds config flow for TeamTracker."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    CONF_TIMEOUT,
    DEFAULT_CONFERENCE_ID,
    DEFAULT_LEAGUE,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LEAGUE_LIST,
)

JSON_FEATURES = "features"
JSON_PROPERTIES = "properties"
JSON_ID = "id"

_LOGGER = logging.getLogger(__name__)


def _get_schema(
    hass: HomeAssistant,
    user_input: Optional[Dict[str, Any]],
    default_dict: Dict[str, Any],
    entry_id: str = None,
) -> vol.Schema:
    # pylint: disable=deprecated-typing-alias
    # pylint: disable=consider-alternative-union-syntax
    """Gets a schema using the default_dict as a backup."""

    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Gets default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(
                CONF_LEAGUE_ID, default=_get_default(CONF_LEAGUE_ID)
            ): cv.string,
            vol.Required(CONF_TEAM_ID, default=_get_default(CONF_TEAM_ID)): cv.string,
            vol.Optional(CONF_NAME, default=_get_default(CONF_NAME)): cv.string,
            vol.Optional(CONF_TIMEOUT, default=_get_default(CONF_TIMEOUT)): int,
            vol.Optional(
                CONF_CONFERENCE_ID, default=_get_default(CONF_CONFERENCE_ID)
            ): cv.string,
        }
    )


def _get_path_schema(hass: Any, user_input: list, default_dict: list) -> Any:
    """Gets a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key):
        """Gets default value for key."""
        return user_input.get(key, default_dict.get(key))

    return vol.Schema(
        {
            vol.Required(CONF_SPORT_PATH, default=_get_default(CONF_SPORT_PATH)): str,
            vol.Required(CONF_LEAGUE_PATH, default=_get_default(CONF_LEAGUE_PATH)): str,
        }
    )


@config_entries.HANDLERS.register(DOMAIN)
class TeamTrackerScoresFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for TeamTracker."""

    VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            league_id = user_input[CONF_LEAGUE_ID].upper()
            if league_id == "XXX":
                self._data.update(user_input)
                return await self.async_step_path()
            for league in LEAGUE_LIST:
                if league[0] == league_id:
                    user_input.update({CONF_SPORT_PATH: league[1]})
                    user_input.update({CONF_LEAGUE_PATH: league[2]})
                    self._data.update(user_input)
                    return self.async_create_entry(
                        title=self._data[CONF_NAME], data=self._data
                    )
            self._errors["base"] = "league"
        return await self._show_config_form(user_input)

    async def async_step_path(self, user_input: Optional[Dict[str, Any]] = None):
        # pylint: disable=deprecated-typing-alias
        # pylint: disable=consider-alternative-union-syntax

        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return await self._show_path_form(user_input)

    async def _show_config_form(self, user_input):
        """Show the configuration form to edit location data."""

        # Defaults
        defaults = {
            CONF_LEAGUE_ID: DEFAULT_LEAGUE,
            CONF_NAME: DEFAULT_NAME,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_TEAM_ID: "",
            CONF_CONFERENCE_ID: DEFAULT_CONFERENCE_ID,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=_get_schema(self.hass, user_input, defaults),
            errors=self._errors,
        )

    async def _show_path_form(self, user_input):
        """Show the path form to edit path data."""

        # Defaults
        defaults = {
            CONF_SPORT_PATH: "",
            CONF_LEAGUE_PATH: "",
        }
        return self.async_show_form(
            step_id="path",
            data_schema=_get_path_schema(self.hass, user_input, defaults),
            errors=self._errors,
        )
