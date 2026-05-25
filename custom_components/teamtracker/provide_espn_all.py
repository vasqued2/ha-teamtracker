""" Provide response from ESPN APIs for league_path = all & team_id is an integer """
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import re
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from .const import API_LIMIT
from .provide_espn import EspnProvider
from .utils import has_team, season_slug_to_name

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_ESPN_ALL_LEAGUES = "espn-all_leagues"
ESPNALL_DATA_FORMAT = "espnall-json"
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"


class EspnAllLeaguesProvider(EspnProvider):
    """Provider for ESPN data when league_path is all and team_id is an integer."""


    #
    #  __init__()
    #    Reuse EspnProvider settings except:
    #      - DATA_PROVIDER
    #      - async_fetch_scoreboard_data()
    #
    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_ESPN_ALL_LEAGUES
        self.TEAM_SCHEDULE_KEY: str = "team-schedule-key"
        self.data_format = ESPNALL_DATA_FORMAT
        self.lookups: dict[str, list] = {}
        self.instance_cache: dict[str, dict] = {}


    #
    #  _get_cache_key()
    #    Return unique key for espn all calls
    #
    def _get_cache_key(self) -> str:
        """Return cache key"""

        if not self._coordinator:
            return ""

        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        conference_id = self._coordinator.conference_id
        team_id = self._coordinator.team_id

        lang = self._coordinator.get_lang()

        # For "all" leagues, include team_id in cache key since each team
        # uses different narrow date windows for the scoreboard call.
        key = self.DATA_PROVIDER + ":" + sport_path + ":" + league_path + ":" + conference_id + ":" + lang + ":" + team_id

        return key


    #
    #  async_fetch_scoreboard_data()
    #    ESPN APIs returning all leagues quickly hit the API_LIMIT, so force use of tight date ranges
    #      1. Get the team schedule from ESPN and determine next upcoming game
    #      2. Call w/ date range up to upcoming game
    #      2. Call w/ date range around upcoming game
    #
    async def async_fetch_scoreboard_data(
        self, 
        hass: HomeAssistant, 
        lang: str,
    ) -> dict:
        """Gets data from ESPN APIs for all leagues in specified sport."""

        if not self._coordinator:
            return{"data": None, "url": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        team_id = self._coordinator.team_id.upper()

        # Get date of next game
        schedule_info = await self._async_get_team_schedule()
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

        url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/scoreboard"

        response = await self.async_call_espn_api(hass, url, url_parms, sensor_name, team_id)
        data = response["data"]

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
                    url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/scoreboard"

                    response = await self.async_call_espn_api(hass, url, url_parms, sensor_name, team_id)

        # Add required lookup tables
        if "team_list" not in self.lookups:
            teams_response = await self.async_fetch_team_data(hass, sport_path, league_path, sensor_name)
            teams_data = teams_response["data"]
            self.lookups["team_list"] = teams_data
        response["lookups"] = self.lookups


        return response


    #
    #  _async_get_team_schedule()
    #
    #    Calls the team info and schedule endpoints to discover the next game
    #    date and build an event_id → league name mapping (substring of season)
    #    Results are cached in the instance_cache until the next game date passes.
    #
    async def _async_get_team_schedule(self):
        """Fetch team schedule info for 'all' league date computation."""

        team_id = self._coordinator.team_id
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        sensor_name = self._coordinator.name

        today = date.today()
        cache = self.instance_cache.get(self.TEAM_SCHEDULE_KEY)

        if cache is not None and today <= cache["expires"]:
            _LOGGER.debug("%s: instance_cache hit for '%s'", sensor_name, team_id)
            self.lookups["derived_league_name"] = cache["derived_league_name"]
            return cache

        team_url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/teams/{team_id}"

        next_events = []

        response = await self.async_call_espn_api(self._coordinator.hass, team_url, None, sensor_name, team_id)
        team_data = response["data"]

        # Try to derive the league_name from the season name or slug 
        #   since not available from scoreboard API w/ league = "all"
        season_name = ""
        if team_data:
            next_events = team_data.get("team", {}).get("nextEvent", [])
            for ne in next_events:
                eid = ne.get("id")
                if not eid:
                    continue
                season_name = ne.get("season", {}).get("displayName") or season_slug_to_name(
                    ne.get("season", {}).get("slug", "")
                )

        schedule_url = team_url + "/schedule"
        response = await self.async_call_espn_api(self._coordinator.hass, schedule_url, None, sensor_name, team_id)
        sched_data = response["data"]
        if sched_data:
            for e in sched_data.get("events", []):
                eid = e.get("id")
                if not eid:
                    continue
                season_name = e.get("season", {}).get("displayName") or season_slug_to_name(
                    e.get("season", {}).get("slug", "")
                )

        derived_league_name = re.sub(r"^\d{4}(-\d{2})?\s+", "", season_name)

        self.lookups["derived_league_name"] = derived_league_name
        next_game_date = (
            date.fromisoformat(next_events[0]["date"][:10]) if next_events else None
        )

        result = {
            "next_game_date": next_game_date,
            "derived_league_name": derived_league_name,
            "expires": next_game_date or today,
        }
        self.instance_cache[self.TEAM_SCHEDULE_KEY] = result
        return result