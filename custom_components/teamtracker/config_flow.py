"""Adds config flow for TeamTracker."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_LANGUAGE,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    DEFAULT_CONFERENCE_ID,
    DEFAULT_LEAGUE,
    DOMAIN,
    LEAGUE_MAP,
)

_LOGGER = logging.getLogger(__name__)

_LEAGUE_NAMES: dict[str, str] = {
    "AFL":      "Australian Football League",
    "ATP":      "ATP Tour",
    "BUND":     "Bundesliga",
    "CL":       "UEFA Champions League",
    "CLA":      "Copa Libertadores",
    "EPL":      "Premier League",
    "F1":       "Formula 1",
    "IRL":      "IndyCar Series",
    "LIGA":     "La Liga",
    "LIG1":     "Ligue 1",
    "MLB":      "Major League Baseball",
    "MLS":      "Major League Soccer",
    "NASCAR":   "NASCAR Cup Series",
    "NBA":      "National Basketball Association",
    "NCAAF":    "College Football",
    "NCAAM":    "NCAA Men's Basketball",
    "NCAAVB":   "NCAA Men's Volleyball",
    "NCAAVBW":  "NCAA Women's Volleyball",
    "NCAAW":    "NCAA Women's Basketball",
    "NFL":      "National Football League",
    "NHL":      "National Hockey League",
    "NWSL":     "National Women's Soccer League",
    "PGA":      "PGA Tour",
    "SERA":     "Serie A",
    "UFC":      "Ultimate Fighting Championship",
    "WC":       "FIFA World Cup",
    "WNBA":     "Women's National Basketball Association",
    "WTA":      "WTA Tour",
    "WWC":      "FIFA Women's World Cup",
    "XFL":      "XFL",
}

LEAGUE_OPTIONS = {
    k: f"{k} \u2013 {_LEAGUE_NAMES.get(k, k)}"
    for k in sorted(LEAGUE_MAP)
}
LEAGUE_OPTIONS["XXX"] = "XXX \u2013 Custom API"


async def _fetch_teams(hass: HomeAssistant, league_id: str) -> list[dict]:
    """Fetch teams from ESPN API for a given league."""
    if league_id not in LEAGUE_MAP:
        return []
    paths = LEAGUE_MAP[league_id]
    sport = paths[CONF_SPORT_PATH]
    league = paths[CONF_LEAGUE_PATH]
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{sport}/{league}/teams?limit=200"
    )
    session = async_get_clientsession(hass)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
    except Exception as err:
        _LOGGER.warning("ESPN teams fetch failed: %s", err)
        return []

    raw = (
        data.get("sports", [{}])[0]
        .get("leagues", [{}])[0]
        .get("teams", [])
    )
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
    return teams


def _get_path_schema(
    user_input: dict[str, Any] | None,
    default_dict: dict[str, Any],
) -> vol.Schema:
    """Schema for custom sport/league path step."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str) -> Any:
        return user_input.get(key, default_dict.get(key, ""))

    return vol.Schema(
        {
            vol.Required(CONF_SPORT_PATH, default=_get_default(CONF_SPORT_PATH)): str,
            vol.Required(CONF_LEAGUE_PATH, default=_get_default(CONF_LEAGUE_PATH)): str,
            vol.Required(CONF_TEAM_ID, default=_get_default(CONF_TEAM_ID)): cv.string,
            vol.Optional(CONF_CONFERENCE_ID, default=_get_default(CONF_CONFERENCE_ID)): cv.string,
            vol.Optional(CONF_NAME, default=_get_default(CONF_NAME)): cv.string,
        }
    )


class TeamTrackerScoresFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for TeamTracker."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize."""
        self._league_id: str = ""
        self._all_teams: list[dict] = []
        self._search_results: dict[str, str] = {}  # label -> abbreviation
        self._team_meta: dict[str, dict] = {}       # abbreviation -> full info
        self._errors: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    #  Step 1: choose league + optional search term                       #
    # ------------------------------------------------------------------ #
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self._league_id = user_input[CONF_LEAGUE_ID].upper()

            if self._league_id == "XXX":
                return await self.async_step_path()

            search_term = user_input.get("search_team", "").strip().lower()

            if search_term:
                self._all_teams = await _fetch_teams(self.hass, self._league_id)
                if not self._all_teams:
                    self._errors["base"] = "cannot_fetch_teams"
                else:
                    filtered = [
                        t for t in self._all_teams
                        if search_term in t["displayName"].lower()
                        or search_term in t["abbreviation"].lower()
                        or search_term in t["location"].lower()
                    ]
                    if not filtered:
                        self._errors["search_team"] = "no_teams_found"
                    else:
                        self._search_results = {
                            t["abbreviation"]: f"{t['displayName']} ({t['abbreviation']})"
                            for t in filtered
                        }
                        self._team_meta = {t["abbreviation"]: t for t in filtered}
                        return await self.async_step_select_team()
            else:
                return await self.async_step_manual()

        schema = vol.Schema(
            {
                vol.Required(CONF_LEAGUE_ID, default=DEFAULT_LEAGUE): vol.In(LEAGUE_OPTIONS),
                vol.Optional("search_team", default=""): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=self._errors,
        )

    # ------------------------------------------------------------------ #
    #  Step 2a: pick from search results                                  #
    # ------------------------------------------------------------------ #
    async def async_step_select_team(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle team selection from search results."""
        if user_input is not None:
            abbr = user_input["team_selection"]
            meta = self._team_meta.get(abbr, {})
            conf_id = str(meta.get("conference_id", ""))
            paths = LEAGUE_MAP[self._league_id]
            name = meta.get("displayName", abbr)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME:          name,
                    CONF_LEAGUE_ID:     self._league_id,
                    CONF_TEAM_ID:       abbr,
                    CONF_CONFERENCE_ID: conf_id,
                    CONF_SPORT_PATH:    paths[CONF_SPORT_PATH],
                    CONF_LEAGUE_PATH:   paths[CONF_LEAGUE_PATH],
                },
            )

        schema = vol.Schema(
            {vol.Required("team_selection"): vol.In(self._search_results)}
        )
        return self.async_show_form(
            step_id="select_team",
            data_schema=schema,
            errors={},
        )

    # ------------------------------------------------------------------ #
    #  Step 2b: manual team_id entry (no search / fallback)              #
    # ------------------------------------------------------------------ #
    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle manual team ID entry."""
        if user_input is not None:
            paths = LEAGUE_MAP[self._league_id]
            name = user_input.get(CONF_NAME) or user_input[CONF_TEAM_ID]
            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME:          name,
                    CONF_LEAGUE_ID:     self._league_id,
                    CONF_TEAM_ID:       user_input[CONF_TEAM_ID],
                    CONF_CONFERENCE_ID: user_input.get(CONF_CONFERENCE_ID, DEFAULT_CONFERENCE_ID),
                    CONF_SPORT_PATH:    paths[CONF_SPORT_PATH],
                    CONF_LEAGUE_PATH:   paths[CONF_LEAGUE_PATH],
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_TEAM_ID): cv.string,
                vol.Optional(CONF_CONFERENCE_ID, default=DEFAULT_CONFERENCE_ID): cv.string,
                vol.Optional(CONF_NAME, default=""): cv.string,
            }
        )
        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            errors={},
        )

    # ------------------------------------------------------------------ #
    #  Step 2c: Custom API (league_id = XXX)                             #
    # ------------------------------------------------------------------ #
    async def async_step_path(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle custom sport/league path configuration."""
        self._errors = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME) or user_input[CONF_TEAM_ID]
            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME:          name,
                    CONF_LEAGUE_ID:     "XXX",
                    CONF_TEAM_ID:       user_input[CONF_TEAM_ID],
                    CONF_CONFERENCE_ID: user_input.get(CONF_CONFERENCE_ID, DEFAULT_CONFERENCE_ID),
                    CONF_SPORT_PATH:    user_input[CONF_SPORT_PATH],
                    CONF_LEAGUE_PATH:   user_input[CONF_LEAGUE_PATH],
                },
            )

        defaults = {CONF_SPORT_PATH: "", CONF_LEAGUE_PATH: ""}
        return self.async_show_form(
            step_id="path",
            data_schema=_get_path_schema(user_input, defaults),
            errors=self._errors,
        )

    # ------------------------------------------------------------------ #
    #  Options flow (reconfigure existing entry)                          #
    # ------------------------------------------------------------------ #
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return TeamTrackerScoresOptionsFlow(config_entry)


class TeamTrackerScoresOptionsFlow(config_entries.OptionsFlow):
    """Options flow for TeamTracker."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.entry = config_entry
        self._options: dict[str, Any] = dict(config_entry.options)
        self._errors: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage options."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        lang = None
        if (
            self.entry
            and self.entry.options
            and CONF_API_LANGUAGE in self.entry.options
        ):
            lang = self.entry.options[CONF_API_LANGUAGE]

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_API_LANGUAGE,
                    description={"suggested_value": lang},
                    default="",
                ): cv.string,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=self._errors,
        )
