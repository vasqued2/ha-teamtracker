from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import re
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from .const import (
    API_LIMIT,
)
from .espn import EspnProvider
from .utils import async_call_espn_api, has_team

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_ESPN_ALL_LEAGUES = "espn-all_leagues"
URL_HEAD = "http://site.api.espn.com/apis/site/v2/sports/"
URL_TAIL = "/scoreboard"


class EspnAllLeaguesProvider(EspnProvider):
    """Provider for ESPN data."""

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_ESPN_ALL_LEAGUES


    def _slug_to_name(self, slug: str) -> str:
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

    #
    #  async_get_team_schedule()
    #
    #    Calls the team info and schedule endpoints to discover the next game
    #    date and build an event_id → league name mapping (substring of season)
    #    Results are cached in all_team_cache until the next game date passes.
    #
    async def async_get_team_schedule(self):
        """Fetch team schedule info for 'all' league date computation."""

        team_id = self._coordinator.team_id
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        sensor_name = self._coordinator.name

        cache_key = f"{sport_path}:{league_path}:{team_id}"
        today = date.today()
        cached = self._coordinator.all_team_cache.get(cache_key) # get the class variable

        if cached is not None and today <= cached["expires"]:
            _LOGGER.debug("%s: all_team_cache hit for '%s'", sensor_name, team_id)
            return cached

        team_url = URL_HEAD + sport_path + "/" + league_path + "/teams/" + team_id

        league_map = {}
        next_events = []

        response = await async_call_espn_api(self._coordinator.hass, team_url, None, sensor_name, team_id)
        team_data = response["data"]
        if team_data:
            next_events = team_data.get("team", {}).get("nextEvent", [])
            for ne in next_events:
                eid = ne.get("id")
                if not eid:
                    continue
                display = ne.get("season", {}).get("displayName") or self._slug_to_name(
                    ne.get("season", {}).get("slug", "")
                )
                if display:
                    league_map[str(eid)] = display

        schedule_url = team_url + "/schedule"
        response = await async_call_espn_api(self._coordinator.hass, schedule_url, None, sensor_name, team_id)
        sched_data = response["data"]
        if sched_data:
            for e in sched_data.get("events", []):
                eid = e.get("id")
                if not eid:
                    continue
                display = e.get("season", {}).get("displayName") or self._slug_to_name(
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
        self._coordinator.all_team_cache[cache_key] = result  #update the class variable
        return result



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
        schedule_info = await self.async_get_team_schedule()
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

