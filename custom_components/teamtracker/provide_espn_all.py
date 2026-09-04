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
    #  _async_fetch_scoreboard_data()
    #    ESPN APIs returning all leagues quickly hit the API_LIMIT, so force use of tight date ranges
    #      1. Get the team schedule from ESPN and determine next upcoming game
    #      2. Call w/ date range up to upcoming game
    #      2. Call w/ date range around upcoming game
    #
    async def _async_fetch_scoreboard_data(
        self, 
        hass: HomeAssistant, 
        lang: str,
    ) -> dict:
        """Gets data from ESPN APIs for all leagues in specified sport."""

        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

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

        # ESPN's sport-wide /all scoreboard can omit a team's competition even
        # though the already-fetched team schedule contains the full event.
        # Reuse that cached response only when /all still does not contain the
        # configured team, and restrict it to the same requested date window.
        # ESPN's sport-wide ALL scoreboard can omit a team's competition.
        # Keep it primary, then reuse already-fetched team-specific sources.
        # This is generic for every numeric team configured with league_path=all.
        if has_team(response.get("data"), team_id) is False:
            next_event_response = self._next_event_response_for_dates(
                schedule_info, url_parms["dates"], response
            )
            if next_event_response and has_team(
                next_event_response.get("data"), team_id
            ):
                response = next_event_response
                self._set_fallback_derived_league_name(response)
            else:
                schedule_response = self._schedule_response_for_dates(
                    schedule_info, url_parms["dates"]
                )
                if schedule_response and has_team(
                    schedule_response.get("data"), team_id
                ):
                    response = schedule_response
                    self._set_fallback_derived_league_name(response)

        # Add required lookup tables
        if "team_list" not in self.lookups:
            teams_response = await self.async_get_team_data(hass, sport_path, league_path, sensor_name)
            teams_data = teams_response["data"]
            self.lookups["team_list"] = teams_data
        response["lookups"] = self.lookups


        return response


    @staticmethod
    def _next_event_response_for_dates(
        schedule_info, date_range, scoreboard_response
    ):
        """Return cached team.nextEvent entries inside the requested date range."""
        if not schedule_info:
            return None

        next_events = schedule_info.get("next_events") or []
        if not next_events:
            return None

        try:
            start_date, end_date = date_range.split("-", 1)
        except (AttributeError, ValueError):
            return None

        events = []
        for event in next_events:
            event_date = str(event.get("date", ""))[:10].replace("-", "")
            if len(event_date) != 8 or not start_date <= event_date <= end_date:
                continue

            # team.nextEvent is ESPN data, but its shape differs slightly
            # from scoreboard. Normalize only ESPN-provided equivalents.
            normalized_event = dict(event)

            season = event.get("season")
            season_type = event.get("seasonType")
            if isinstance(season, dict):
                normalized_season = dict(season)
                if (
                    not normalized_season.get("slug")
                    and isinstance(season_type, dict)
                    and season_type.get("name")
                ):
                    normalized_season["slug"] = re.sub(
                        r"[^a-z0-9]+",
                        "-",
                        str(season_type["name"]).lower(),
                    ).strip("-")
                normalized_event["season"] = normalized_season

            normalized_competitions = []
            for competition in event.get("competitions") or []:
                if not isinstance(competition, dict):
                    continue
                normalized_competition = dict(competition)
                normalized_competitors = []

                for competitor in competition.get("competitors") or []:
                    if not isinstance(competitor, dict):
                        continue
                    normalized_competitor = dict(competitor)
                    team = competitor.get("team")

                    if isinstance(team, dict):
                        normalized_team = dict(team)
                        if not normalized_team.get("logo"):
                            for logo in normalized_team.get("logos") or []:
                                if isinstance(logo, dict) and logo.get("href"):
                                    normalized_team["logo"] = logo["href"]
                                    break
                        normalized_competitor["team"] = normalized_team

                    normalized_competitors.append(normalized_competitor)

                normalized_competition["competitors"] = normalized_competitors
                normalized_competitions.append(normalized_competition)

            normalized_event["competitions"] = normalized_competitions
            events.append(normalized_event)

        if not events:
            return None

        fallback_response = dict(scoreboard_response)
        fallback_data = dict(scoreboard_response.get("data") or {})
        fallback_data["events"] = events
        fallback_response["data"] = fallback_data

        team_response = schedule_info.get("team_response") or {}
        if team_response.get("url"):
            fallback_response["url"] = team_response["url"]
        if team_response.get("timestamp") is not None:
            fallback_response["timestamp"] = team_response["timestamp"]

        return fallback_response


    def _set_fallback_derived_league_name(self, response):
        """Set ALL league-name lookup from the event actually selected."""
        events = (response.get("data") or {}).get("events") or []
        if not events:
            return

        event = events[0]
        season = event.get("season") or {}
        season_name = str(season.get("displayName") or "").strip()
        if not season_name:
            season_name = season_slug_to_name(str(season.get("slug") or ""))

        derived = re.sub(r"^\d{4}(-\d{2})?\s+", "", season_name).strip()
        if derived:
            self.lookups["derived_league_name"] = derived

    @staticmethod
    def _schedule_response_for_dates(schedule_info, date_range):
        """Return cached team-schedule events inside the requested date range."""
        if not schedule_info:
            return None

        schedule_response = schedule_info.get("schedule_response")
        schedule_data = schedule_response.get("data") if schedule_response else None
        if not schedule_data:
            return None

        try:
            start_date, end_date = date_range.split("-", 1)
        except (AttributeError, ValueError):
            return None

        events = []
        for event in schedule_data.get("events", []):
            event_date = str(event.get("date", ""))[:10].replace("-", "")
            if len(event_date) == 8 and start_date <= event_date <= end_date:
                events.append(event)

        if not events:
            return None

        fallback_response = dict(schedule_response)
        fallback_data = dict(schedule_data)
        fallback_data["events"] = events
        fallback_response["data"] = fallback_data
        return fallback_response


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
        team_response = response
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
        # team.nextEvent on the aggregate "all" endpoint is not complete for
        # every soccer league. The team schedule is already fetched above and is
        # the more complete source, so also derive the earliest non-completed
        # current/future event from it. This keeps the scoreboard/fallback date
        # window wide enough when nextEvent is missing.
        candidate_dates = []

        for event in next_events:
            try:
                event_date = date.fromisoformat(str(event.get("date", ""))[:10])
            except (TypeError, ValueError):
                continue
            if event_date >= today:
                candidate_dates.append(event_date)

        if sched_data:
            for event in sched_data.get("events", []):
                status_type = event.get("status", {}).get("type", {})
                if status_type.get("completed") is True:
                    continue
                try:
                    event_date = date.fromisoformat(str(event.get("date", ""))[:10])
                except (TypeError, ValueError):
                    continue
                if event_date >= today:
                    candidate_dates.append(event_date)

        next_game_date = min(candidate_dates) if candidate_dates else None

        result = {
            "next_game_date": next_game_date,
            "derived_league_name": derived_league_name,
            "expires": next_game_date or today,
            "schedule_response": response,
            "team_response": team_response,
            "next_events": next_events,
            "sport_path": self._coordinator.sport_path,
        }
        self.instance_cache[self.TEAM_SCHEDULE_KEY] = result
        return result