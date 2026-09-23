""" Provide response from ESPN APIs for league_path = all & team_id is an integer """
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
import logging
import re
from typing import TYPE_CHECKING
from urllib.parse import unquote

from homeassistant.core import HomeAssistant

from .const import API_LIMIT, CONF_LEAGUE_PATH, CONF_SPORT_PATH, NATIVE_LEAGUES
from .provide_espn import EspnProvider
from .utils import has_team, season_slug_to_name

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

DATA_PROVIDER_ESPN_ALL_LEAGUES = "espn-all_leagues"
ESPNALL_DATA_FORMAT = "espnall-json"
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_CORE_BASE_URL = "https://sports.core.api.espn.com"


class EspnAllLeaguesProvider(EspnProvider):
    """Provider for ESPN data when league_path is all and team_id is an integer."""

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_ESPN_ALL_LEAGUES
        self.TEAM_SCHEDULE_KEY: str = "team-schedule-key"
        self.data_format = ESPNALL_DATA_FORMAT
        self.lookups: dict[str, list] = {}
        self.instance_cache: dict[str, dict] = {}

    def _get_cache_key(self) -> str:
        """Return cache key."""
        if not self._coordinator:
            return ""

        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        conference_id = self._coordinator.conference_id
        team_id = self._coordinator.team_id
        lang = self._coordinator.get_lang()

        # For "all" leagues, include team_id in cache key since each team
        # uses different narrow date windows for the scoreboard call.
        return (
            self.DATA_PROVIDER
            + ":"
            + sport_path
            + ":"
            + league_path
            + ":"
            + conference_id
            + ":"
            + lang
            + ":"
            + team_id
        )

    @staticmethod
    def _soccer_teams_from_payload(payload: dict | None) -> list[dict]:
        """Extract canonical teams from one ESPN soccer league response."""
        if not isinstance(payload, dict):
            return []

        teams: dict[str, dict] = {}
        for sport in payload.get("sports") or []:
            if not isinstance(sport, dict):
                continue
            for league in sport.get("leagues") or []:
                if not isinstance(league, dict):
                    continue
                for wrapper in league.get("teams") or []:
                    if not isinstance(wrapper, dict):
                        continue
                    team = (
                        wrapper.get("team")
                        if isinstance(wrapper.get("team"), dict)
                        else wrapper
                    )
                    if not isinstance(team, dict):
                        continue
                    team_id = str(team.get("id") or "").strip()
                    display_name = str(
                        team.get("displayName") or team.get("name") or ""
                    ).strip()
                    if not team_id or not display_name:
                        continue
                    teams[team_id] = {
                        "id": team_id,
                        "displayName": display_name,
                        "abbreviation": str(team.get("abbreviation") or "").strip(),
                        "location": str(team.get("location") or "").strip(),
                    }
        return list(teams.values())

    async def _async_fetch_team_data(
        self,
        hass: HomeAssistant,
        sport_path: str,
        league_path: str,
        sensor_name: str,
    ) -> dict:
        """Fetch teams, with soccer/all discovery isolated in this provider."""
        # The broad league-catalog crawl exists only to support config-flow team
        # discovery. Runtime providers already have a configured team and must
        # never enumerate every soccer league just to populate lookups.
        if (
            sport_path != "soccer"
            or league_path != "all"
            or self._coordinator is not None
        ):
            return await super()._async_fetch_team_data(
                hass,
                sport_path,
                league_path,
                sensor_name,
            )

        league_paths: set[str] = set()
        for values in NATIVE_LEAGUES.values():
            if values.get(CONF_SPORT_PATH) != "soccer":
                continue
            path = str(values.get(CONF_LEAGUE_PATH) or "").strip()
            if path and path != "all":
                league_paths.add(path)

        catalog_url = f"{ESPN_CORE_BASE_URL}/v2/sports/soccer/leagues"
        catalog_response = await self.async_call_espn_api(
            hass,
            catalog_url,
            {"limit": "1000"},
            sensor_name,
            "soccer-all",
        )
        catalog = catalog_response.get("data")
        if isinstance(catalog, dict):
            for item in catalog.get("items") or []:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("slug") or "").strip()
                ref = str(item.get("$ref") or "")
                if not path and ref:
                    match = re.search(r"/leagues/([^/?#]+)", ref)
                    if match:
                        path = unquote(match.group(1))
                if path and path != "all":
                    league_paths.add(path)

        semaphore = asyncio.Semaphore(12)

        async def fetch(path: str) -> list[dict]:
            async with semaphore:
                response = await self.async_call_espn_api(
                    hass,
                    f"{ESPN_BASE_URL}/soccer/{path}/teams",
                    {"limit": "1000"},
                    sensor_name,
                    path,
                )
                return self._soccer_teams_from_payload(response.get("data"))

        responses = await asyncio.gather(*(fetch(path) for path in sorted(league_paths)))

        teams: dict[str, dict] = {}
        for response in responses:
            for team in response:
                team_id = str(team.get("id") or "").strip()
                if team_id:
                    teams.setdefault(team_id, team)

        result = sorted(
            teams.values(),
            key=lambda team: str(team.get("displayName") or "").casefold(),
        )
        return {
            "data": result,
            "url": catalog_response.get("url"),
            "timestamp": catalog_response.get("timestamp"),
        }

    @staticmethod
    def _normalize_scoreboard_response(response):
        """Keep ALL fallbacks usable when a scoreboard call returns no data."""
        normalized = dict(response) if isinstance(response, dict) else {}
        if not isinstance(normalized.get("data"), dict):
            normalized["data"] = {}
        normalized.setdefault("url", None)
        normalized.setdefault("timestamp", None)
        return normalized

    async def _async_fetch_scoreboard_data(
        self,
        hass: HomeAssistant,
        lang: str,
    ) -> dict:
        """Get data from ESPN APIs for all leagues in the specified sport."""
        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        team_id = self._coordinator.team_id.upper()

        schedule_info = await self._async_get_team_schedule()
        next_game_date = schedule_info.get("next_game_date") if schedule_info else None

        today_utc = datetime.now(timezone.utc).date()
        day_before_yesterday = today_utc - timedelta(days=2)

        d1 = day_before_yesterday.strftime("%Y%m%d")
        if next_game_date and next_game_date <= today_utc + timedelta(days=7):
            d2 = next_game_date.strftime("%Y%m%d")
        else:
            d2 = today_utc.strftime("%Y%m%d")

        _LOGGER.debug(
            "%s: All-league scoreboard call 1/1 dates=%s-%s (next_game=%s)",
            sensor_name,
            d1,
            d2,
            next_game_date.isoformat() if next_game_date else "unknown",
        )

        url_parms = {
            "lang": lang[:2],
            "limit": str(API_LIMIT),
            "dates": f"{d1}-{d2}",
        }
        url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/scoreboard"

        response = self._normalize_scoreboard_response(
            await self.async_call_espn_api(
                hass,
                url,
                url_parms,
                sensor_name,
                team_id,
            )
        )
        data = response["data"]

        broad_window_truncated = (
            isinstance(data, dict)
            and len(data.get("events") or []) >= API_LIMIT
            and has_team(data, team_id) is False
        )

        if has_team(data, team_id) is False:
            if next_game_date and next_game_date > today_utc:
                nd1 = (next_game_date - timedelta(days=1)).strftime("%Y%m%d")
                nd2 = next_game_date.strftime("%Y%m%d")
                if nd1 != d1 or nd2 != d2:
                    _LOGGER.debug(
                        "%s: All-league scoreboard call 2/2 dates=%s-%s (fallback to next game)",
                        sensor_name,
                        nd1,
                        nd2,
                    )
                    url_parms["dates"] = f"{nd1}-{nd2}"
                    response = self._normalize_scoreboard_response(
                        await self.async_call_espn_api(
                            hass,
                            url,
                            url_parms,
                            sensor_name,
                            team_id,
                        )
                    )

        if broad_window_truncated:
            recent_start = (today_utc - timedelta(days=1)).strftime("%Y%m%d")
            recent_end = today_utc.strftime("%Y%m%d")

            recent_schedule_response = self._schedule_response_for_dates(
                schedule_info,
                f"{recent_start}-{recent_end}",
            )
            next_event_response = self._next_event_response_for_dates(
                schedule_info,
                url_parms["dates"],
                response,
            )
            handoff_response = self._merge_handoff_responses(
                recent_schedule_response,
                next_event_response,
            )

            if handoff_response and has_team(
                handoff_response.get("data"), team_id
            ):
                response = handoff_response
                self._set_fallback_derived_league_name(response)

        if has_team(response.get("data"), team_id) is False:
            next_event_response = self._next_event_response_for_dates(
                schedule_info,
                url_parms["dates"],
                response,
            )
            if next_event_response and has_team(
                next_event_response.get("data"), team_id
            ):
                response = next_event_response
                self._set_fallback_derived_league_name(response)
            else:
                schedule_response = self._schedule_response_for_dates(
                    schedule_info,
                    url_parms["dates"],
                )
                if schedule_response and has_team(
                    schedule_response.get("data"), team_id
                ):
                    response = schedule_response
                    self._set_fallback_derived_league_name(response)

        if "team_list" not in self.lookups:
            if sport_path == "soccer" and league_path == "all":
                self.lookups["team_list"] = self._runtime_team_list(
                    schedule_info,
                    team_id,
                )
            else:
                teams_response = await self.async_get_team_data(
                    hass,
                    sport_path,
                    league_path,
                    sensor_name,
                )
                self.lookups["team_list"] = teams_response["data"]
        response["lookups"] = self.lookups
        return response

    @staticmethod
    def _runtime_team_list(schedule_info, team_id):
        """Build the runtime team lookup from already-fetched team metadata."""
        team_response = (schedule_info or {}).get("team_response") or {}
        team_data = (team_response.get("data") or {}).get("team") or {}
        if (
            not isinstance(team_data, dict)
            or str(team_data.get("id") or "") != team_id
        ):
            return []

        normalized_team = EspnAllLeaguesProvider._normalize_next_event_team(team_data)
        return [
            {
                "id": team_id,
                "displayName": str(
                    normalized_team.get("displayName")
                    or normalized_team.get("name")
                    or ""
                ).strip(),
                "abbreviation": str(
                    normalized_team.get("abbreviation") or ""
                ).strip(),
                "location": str(normalized_team.get("location") or "").strip(),
                "logo": str(normalized_team.get("logo") or "").strip(),
            }
        ]

    @staticmethod
    def _normalize_next_event_team(team):
        """Normalize ESPN-provided team fields used by the scoreboard parser."""
        normalized_team = dict(team)
        if normalized_team.get("logo"):
            return normalized_team

        for logo in normalized_team.get("logos") or []:
            if not isinstance(logo, dict) or not logo.get("href"):
                continue
            normalized_team["logo"] = logo["href"]
            break

        return normalized_team

    @staticmethod
    def _normalize_fallback_event(event):
        """Normalize an ESPN fallback event without inventing missing data."""
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
                score = competitor.get("score")
                if isinstance(score, dict):
                    if score.get("displayValue") is not None:
                        normalized_competitor["score"] = str(
                            score["displayValue"]
                        )
                    elif score.get("value") is not None:
                        normalized_competitor["score"] = str(score["value"])

                team = competitor.get("team")
                if isinstance(team, dict):
                    normalized_competitor["team"] = (
                        EspnAllLeaguesProvider._normalize_next_event_team(team)
                    )
                normalized_competitors.append(normalized_competitor)

            normalized_competition["competitors"] = normalized_competitors
            normalized_competitions.append(normalized_competition)

        normalized_event["competitions"] = normalized_competitions
        return normalized_event

    @staticmethod
    def _normalize_next_event(event):
        """Normalize ESPN nextEvent using the shared fallback normalization."""
        return EspnAllLeaguesProvider._normalize_fallback_event(event)

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
            events.append(EspnAllLeaguesProvider._normalize_next_event(event))

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

    @staticmethod
    def _merge_handoff_responses(schedule_response, next_event_response):
        """Merge recent schedule data and nextEvent for normal parser handoff."""
        if not schedule_response and not next_event_response:
            return None

        events = []
        seen = set()
        for source in (schedule_response, next_event_response):
            if not source:
                continue
            for event in (source.get("data") or {}).get("events") or []:
                if not isinstance(event, dict):
                    continue
                event_id = event.get("id")
                key = (
                    str(event_id)
                    if event_id is not None
                    else str(event.get("date") or "")
                )
                if key in seen:
                    continue
                seen.add(key)
                events.append(event)

        if not events:
            return None

        events.sort(
            key=lambda event: str(
                event.get("date") or "9999-12-31T23:59:59Z"
            )
        )

        fallback_response = dict(next_event_response or schedule_response)
        fallback_data = dict(fallback_response.get("data") or {})
        fallback_data["events"] = events
        fallback_response["data"] = fallback_data

        if schedule_response:
            if schedule_response.get("url"):
                fallback_response["url"] = schedule_response["url"]
            if schedule_response.get("timestamp") is not None:
                fallback_response["timestamp"] = schedule_response["timestamp"]

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
                events.append(
                    EspnAllLeaguesProvider._normalize_fallback_event(event)
                )

        if not events:
            return None

        fallback_response = dict(schedule_response)
        fallback_data = dict(schedule_data)
        fallback_data["events"] = events
        fallback_response["data"] = fallback_data
        return fallback_response

    async def _async_get_team_schedule(self):
        """Fetch team schedule info for 'all' league date computation."""
        team_id = self._coordinator.team_id
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        sensor_name = self._coordinator.name

        now = datetime.now(timezone.utc)
        today = now.date()
        cache = self.instance_cache.get(self.TEAM_SCHEDULE_KEY)

        if cache is not None:
            expires = cache["expires"]
            cache_is_fresh = today < expires

            if today == expires:
                cached_at = cache.get("cached_at")
                if isinstance(cached_at, datetime):
                    cache_age = now - cached_at
                    cache_is_fresh = (
                        timedelta(0) <= cache_age < self.DEFAULT_REFRESH_RATE
                    )

            if cache_is_fresh:
                _LOGGER.debug("%s: instance_cache hit for '%s'", sensor_name, team_id)
                self.lookups["derived_league_name"] = cache["derived_league_name"]
                return cache

        team_url = f"{ESPN_BASE_URL}/{sport_path}/{league_path}/teams/{team_id}"
        next_events = []

        response = await self.async_call_espn_api(
            self._coordinator.hass,
            team_url,
            None,
            sensor_name,
            team_id,
        )
        team_response = response
        team_data = response["data"]

        if team_data:
            next_events = team_data.get("team", {}).get("nextEvent", [])

        schedule_url = team_url + "/schedule"
        response = await self.async_call_espn_api(
            self._coordinator.hass,
            schedule_url,
            None,
            sensor_name,
            team_id,
        )
        sched_data = response["data"]

        candidates = []
        for event in (*next_events, *((sched_data or {}).get("events", []))):
            if not event.get("id"):
                continue
            try:
                event_date = date.fromisoformat(str(event.get("date", ""))[:10])
            except (TypeError, ValueError):
                continue
            season = event.get("season") or {}
            name = season.get("displayName") or season_slug_to_name(
                season.get("slug", "")
            )
            if not name:
                continue
            candidates.append((event_date, name))

        upcoming = [candidate for candidate in candidates if candidate[0] >= today]
        if upcoming:
            season_name = min(upcoming, key=lambda candidate: candidate[0])[1]
        elif candidates:
            season_name = max(candidates, key=lambda candidate: candidate[0])[1]
        else:
            season_name = ""

        derived_league_name = re.sub(
            r"^\d{4}(-\d{2})?\s+",
            "",
            season_name,
        )

        self.lookups["derived_league_name"] = derived_league_name
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
            "cached_at": now,
            "schedule_response": response,
            "team_response": team_response,
            "next_events": next_events,
            "sport_path": self._coordinator.sport_path,
        }
        self.instance_cache[self.TEAM_SCHEDULE_KEY] = result
        return result
