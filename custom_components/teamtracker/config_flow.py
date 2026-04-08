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
    DOMAIN,
    INDIVIDUAL_SPORTS,
    LEAGUE_MAP,
    SOCCER,
)

_LOGGER = logging.getLogger(__name__)


# Sport groups: key → (display_name, {league_id: display_label})
_SPORT_GROUPS: dict[str, tuple[str, dict[str, str]]] = {
    "australian-football": ("Australian Football", {
        "AFL": "AFL",
    }),
    "baseball": ("Baseball", {
        "MLB": "MLB",
    }),
    "basketball": ("Basketball", {
        "NBA": "NBA",
        "NCAAM": "NCAA Men's Basketball",
        "NCAAW": "NCAA Women's Basketball",
        "WNBA": "WNBA",
    }),
    "football": ("Football", {
        "NCAAF": "NCAA Football",
        "NFL": "NFL",
        "XFL": "XFL",
    }),
    "golf": ("Golf", {
        "PGA": "PGA Tour",
    }),
    "hockey": ("Hockey", {
        "NHL": "NHL",
    }),
    "mma": ("MMA", {
        "UFC": "UFC",
    }),
    "racing": ("Racing", {
        "F1": "Formula 1",
        "IRL": "IndyCar",
        "NASCAR": "NASCAR Cup Series",
    }),
    "soccer-us": ("Soccer (U.S.)", {
        "MLS": "MLS",
        "NWSL": "NWSL",
    }),
    "soccer-intl": ("Soccer (International)", {
        "BUND": "Bundesliga",
        "CL": "Champions League",
        "CLA": "Copa Libertadores",
        "EPL": "Premier League",
        "LIGA": "La Liga",
        "LIG1": "Ligue 1",
        "SERA": "Serie A",
        "WC": "World Cup",
        "WWC": "Women's World Cup",
    }),
    "tennis": ("Tennis", {
        "ATP": "ATP",
        "WTA": "WTA",
    }),
    "volleyball": ("Volleyball", {
        "NCAAVB": "NCAA Men's Volleyball",
        "NCAAVBW": "NCAA Women's Volleyball",
    }),
}

SPORT_OPTIONS: dict[str, str] = {
    "XXX": "Custom API",
    **{k: v[0] for k, v in _SPORT_GROUPS.items()}
}

def _league_browse_url(league_id: str) -> str:
    """Return an ESPN URL where users can browse teams for a given league."""
    if league_id not in LEAGUE_MAP:
        return "https://www.espn.com"
    paths = LEAGUE_MAP[league_id]
    sport = paths[CONF_SPORT_PATH]
    league = paths[CONF_LEAGUE_PATH]
    if sport == SOCCER:
        return f"https://www.espn.co.uk/football/league/_/name/{league}"
    return f"https://www.espn.com/{league}/teams"


async def _fetch_teams(hass: HomeAssistant, league_id: str) -> list[dict]:
    """Fetch teams from ESPN API for a given league."""
    if league_id not in LEAGUE_MAP:
        return []
    paths = LEAGUE_MAP[league_id]
    sport = paths[CONF_SPORT_PATH]
    league = paths[CONF_LEAGUE_PATH]
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{sport}/{league}/teams?limit=1000"
    )
    session = async_get_clientsession(hass)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as err:
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


async def _fetch_team_conference_id(
    hass: HomeAssistant, league_id: str, team_id: str
) -> str:
    """Fetch conference/group ID for a single team from the ESPN team detail API."""
    if league_id not in LEAGUE_MAP:
        return ""
    paths = LEAGUE_MAP[league_id]
    sport = paths[CONF_SPORT_PATH]
    league = paths[CONF_LEAGUE_PATH]
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports"
        f"/{sport}/{league}/teams/{team_id}"
    )
    session = async_get_clientsession(hass)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.warning("ESPN team detail fetch failed: %s", err)
        return ""
    groups = data.get("team", {}).get("groups") or {}
    return str(groups.get("id", ""))


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
        self._sport_key: str = ""
        self._league_id: str = ""
        self._all_teams: list[dict] = []
        self._search_results: dict[str, str] = {}
        self._team_meta: dict[str, dict] = {}
        self._errors: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    #  Step 1: choose sport group                                         #
    # ------------------------------------------------------------------ #
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            sport_key = user_input["sport_key"]
            if sport_key == "XXX":
                return await self.async_step_custom_api()
            self._sport_key = sport_key
            leagues = _SPORT_GROUPS[sport_key][1]
            if len(leagues) == 1:
                # Only one league for this sport — skip league step
                self._league_id = next(iter(leagues))
                return await self.async_step_search()
            return await self.async_step_league()

        schema = vol.Schema(
            {vol.Required("sport_key"): vol.In(SPORT_OPTIONS)}
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=self._errors,
        )

    # ------------------------------------------------------------------ #
    #  Step 2a: Set Up Custom API (sport_key = XXX)                      #
    # ------------------------------------------------------------------ #
    async def async_step_custom_api(
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
            step_id="custom_api",
            data_schema=_get_path_schema(user_input, defaults),
            errors=self._errors,
        )


    # ------------------------------------------------------------------ #
    #  Step 2b: choose league within sport                               #
    # ------------------------------------------------------------------ #
    async def async_step_league(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle league selection within the chosen sport."""
        self._errors = {}

        if user_input is not None:
            self._league_id = user_input[CONF_LEAGUE_ID]
            return await self.async_step_search()

        league_options = _SPORT_GROUPS[self._sport_key][1]
        sport_name = _SPORT_GROUPS[self._sport_key][0]
        schema = vol.Schema(
            {vol.Required(CONF_LEAGUE_ID): vol.In(league_options)}
        )
        return self.async_show_form(
            step_id="league",
            data_schema=schema,
            errors=self._errors,
            description_placeholders={"sport_name": sport_name},
        )

    # ------------------------------------------------------------------ #
    #  Step 3: search team (ESPN link always correct here)                #
    # ------------------------------------------------------------------ #
    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle team search step."""
        self._errors = {}

        # Individual sports (golf, mma, tennis) have athletes, not teams —
        # the ESPN teams API returns nothing useful, so skip straight to manual.
        sport_path = LEAGUE_MAP.get(self._league_id, {}).get(CONF_SPORT_PATH, "")
        if user_input is None and sport_path in INDIVIDUAL_SPORTS:
            return await self.async_step_manual_athlete(user_input=None)

        if user_input is not None:
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
                return await self.async_step_manual_team()

        schema = vol.Schema(
            {vol.Optional("search_team", default=""): str}
        )
        sport_name = _SPORT_GROUPS.get(self._sport_key, ("",))[0]
        league_name = _SPORT_GROUPS.get(self._sport_key, ("", {}))[1].get(self._league_id, "")
        return self.async_show_form(
            step_id="search",
            data_schema=schema,
            errors=self._errors,
            description_placeholders={
                "league_url": _league_browse_url(self._league_id),
                "league_id": self._league_id,
                "league_name": league_name,
                "sport_name": sport_name,
            },
        )

    # ------------------------------------------------------------------ #
    #  Step 4a: pick from search results                                  #
    # ------------------------------------------------------------------ #
    async def async_step_select_team(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle team selection from search results."""

        ncaa_flag = "NCAA" in self._league_id
        if user_input is not None:
            abbr = user_input["team_selection"]
            meta = self._team_meta.get(abbr, {})
            paths = LEAGUE_MAP[self._league_id]
            name = user_input.get(CONF_NAME, "").strip() or meta.get("displayName", abbr)
            team_id = meta.get("id", abbr)

            entry_data = {
                    CONF_NAME:          name,
                    CONF_LEAGUE_ID:     self._league_id,
                    CONF_TEAM_ID:       team_id,
                    CONF_SPORT_PATH:    paths[CONF_SPORT_PATH],
                    CONF_LEAGUE_PATH:   paths[CONF_LEAGUE_PATH],
                }
            if ncaa_flag:
                conf_id = await _fetch_team_conference_id(self.hass, self._league_id, team_id)
                entry_data[CONF_CONFERENCE_ID] = conf_id

            return self.async_create_entry(
                title=f"{self._league_id} - {name}",
                data=entry_data,
            )

        sport_name = _SPORT_GROUPS.get(self._sport_key, ("",))[0]
        league_name = _SPORT_GROUPS.get(self._sport_key, ("", {}))[1].get(self._league_id, "")
        schema = vol.Schema({
            vol.Required("team_selection"): vol.In(self._search_results),
            vol.Optional(CONF_NAME, default=""): cv.string,
        })
        return self.async_show_form(
            step_id="select_team",
            data_schema=schema,
            errors={},
            description_placeholders={
                "league_id": self._league_id,
                "sport_name": sport_name,
                "league_name": league_name,
            },
        )

    # ------------------------------------------------------------------ #
    #  Step 4b: manual team_id entry (no search / fallback)              #
    # ------------------------------------------------------------------ #
    async def async_step_manual_team(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle manual team ID entry."""

        ncaa_flag = "NCAA" in self._league_id
        if user_input is not None:
            paths = LEAGUE_MAP[self._league_id]
            name = user_input.get(CONF_NAME) or user_input[CONF_TEAM_ID]
            team_id = user_input[CONF_TEAM_ID]
            entry_data = {
                CONF_NAME:          name,
                CONF_LEAGUE_ID:     self._league_id,
                CONF_TEAM_ID:       team_id,
                CONF_SPORT_PATH:    paths[CONF_SPORT_PATH],
                CONF_LEAGUE_PATH:   paths[CONF_LEAGUE_PATH],
            }
            if ncaa_flag:
                conf_id = await _fetch_team_conference_id(self.hass, self._league_id, team_id)
                entry_data[CONF_CONFERENCE_ID] = conf_id
            return self.async_create_entry(
                title=f"{self._league_id} - {name}",
                data=entry_data,
            )

        sport_name = _SPORT_GROUPS.get(self._sport_key, ("",))[0]
        league_name = _SPORT_GROUPS.get(self._sport_key, ("", {}))[1].get(self._league_id, "")

        schema_dict = {
            vol.Required(CONF_TEAM_ID): cv.string,
        }
#        if ncaa_flag:
#            schema_dict[vol.Optional(CONF_CONFERENCE_ID, default=DEFAULT_CONFERENCE_ID)] = cv.string
        schema_dict[vol.Optional(CONF_NAME, default="")] = cv.string

        return self.async_show_form(
            step_id="manual_team",
            data_schema=vol.Schema(schema_dict),
            errors={},
            description_placeholders={
                "league_id": self._league_id,
                "sport_name": sport_name,
                "league_name": league_name,
            },
        )

    # ------------------------------------------------------------------ #
    #  Step 4c: manual athlete entry (no search / fallback)              #
    # ------------------------------------------------------------------ #
    async def async_step_manual_athlete(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle manual team ID entry."""
        if user_input is not None:
            paths = LEAGUE_MAP[self._league_id]
            name = user_input.get(CONF_NAME) or user_input[CONF_TEAM_ID]
            return self.async_create_entry(
                title=f"{self._league_id} - {name}",
                data={
                    CONF_NAME:          name,
                    CONF_LEAGUE_ID:     self._league_id,
                    CONF_TEAM_ID:       user_input[CONF_TEAM_ID],
#                    CONF_CONFERENCE_ID: user_input.get(CONF_CONFERENCE_ID, DEFAULT_CONFERENCE_ID),
                    CONF_SPORT_PATH:    paths[CONF_SPORT_PATH],
                    CONF_LEAGUE_PATH:   paths[CONF_LEAGUE_PATH],
                },
            )

        sport_name = _SPORT_GROUPS.get(self._sport_key, ("",))[0]
        league_name = _SPORT_GROUPS.get(self._sport_key, ("", {}))[1].get(self._league_id, "")
        schema = vol.Schema(
            {
                vol.Required(CONF_TEAM_ID): cv.string,
#                vol.Optional(CONF_CONFERENCE_ID, default=DEFAULT_CONFERENCE_ID): cv.string,
                vol.Optional(CONF_NAME, default=""): cv.string,
            }
        )
        return self.async_show_form(
            step_id="manual_athlete",
            data_schema=schema,
            errors={},
            description_placeholders={
                "league_id": self._league_id,
                "sport_name": sport_name,
                "league_name": league_name,
            },
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
