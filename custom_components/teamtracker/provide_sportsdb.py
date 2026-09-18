"""Provide responses from TheSportsDB APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import re
from typing import TYPE_CHECKING, Any

import aiohttp
import arrow
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SPORTSDB_API_KEY
from .provider_base import BaseSportProvider

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

_LOGGER = logging.getLogger(__name__)

DATA_PROVIDER_SPORTSDB = "sportsdb"
SPORTSDB_DATA_FORMAT = "sportsdb-json"
SPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"
SPORTSDB_FREE_API_KEY = "123"


class SportsDbProvider(BaseSportProvider):
    """Provider for TheSportsDB data."""

    def __init__(
        self, coordinator: TeamTrackerCoordinator | None = None
    ) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER = DATA_PROVIDER_SPORTSDB
        self.data_format = SPORTSDB_DATA_FORMAT
        self.ATTRIBUTION = "Data provided by TheSportsDB.com"
        self.DEFAULT_REFRESH_RATE = timedelta(minutes=10)
        self.RAPID_REFRESH_RATE = timedelta(seconds=30)
        self.lookups: dict[str, Any] = {}

    def _get_cache_key(self) -> str:
        """Return a cache key without exposing the API key."""
        if not self._coordinator:
            return ""

        return ":".join(
            (
                self.DATA_PROVIDER,
                str(self._coordinator.sport_path),
                str(self._coordinator.league_path),
                str(self._coordinator.team_id),
            )
        )

    def _get_api_key(self) -> str:
        """Return configured V1 API key, falling back to the public key."""
        key: Any = SPORTSDB_FREE_API_KEY

        if self._coordinator:
            key = self._coordinator.config.get(
                CONF_SPORTSDB_API_KEY, SPORTSDB_FREE_API_KEY
            )

            entry = self._coordinator.entry
            if (
                entry
                and entry.options
                and CONF_SPORTSDB_API_KEY in entry.options
            ):
                key = (
                    entry.options.get(CONF_SPORTSDB_API_KEY)
                    or SPORTSDB_FREE_API_KEY
                )

        key = str(key or SPORTSDB_FREE_API_KEY).strip().strip("/")
        return key or SPORTSDB_FREE_API_KEY

    async def async_search_teams(
        self,
        hass: HomeAssistant,
        search_term: str,
        api_key: str | None = None,
        sensor_name: str = "ConfigFlow-SportsDB",
    ) -> dict:
        """Search TheSportsDB teams by name."""
        response = await self.async_call_sportsdb_api(
            hass,
            "searchteams.php",
            {"t": search_term},
            sensor_name,
            api_key=api_key,
        )

        payload = response.get("data")
        raw_teams = (
            payload.get("teams")
            if isinstance(payload, dict)
            else None
        )

        teams = []
        for raw_team in raw_teams or []:
            if not isinstance(raw_team, dict):
                continue

            team = self.team_to_standard(raw_team)
            team["sport"] = str(raw_team.get("strSport") or "")
            team["league_id"] = str(raw_team.get("idLeague") or "")
            team["league_name"] = str(raw_team.get("strLeague") or "")
            teams.append(team)

        return {
            "data": teams,
            "url": response.get("url"),
            "timestamp": response.get("timestamp"),
        }


    async def async_lookup_team(
        self,
        hass: HomeAssistant,
        team_id: str,
        api_key: str | None = None,
        sensor_name: str = "ConfigFlow-SportsDB",
    ) -> dict:
        """Lookup one TheSportsDB team by numeric team ID."""
        return await self.async_call_sportsdb_api(
            hass,
            "lookupteam.php",
            {"id": str(team_id)},
            sensor_name,
            api_key=api_key,
        )

    async def _async_fetch_team_data(
        self,
        hass: HomeAssistant,
        sport_path: str,
        league_path: str,
        sensor_name: str,
    ) -> dict:
        """Fetch configured team and return TeamTracker team-list format."""
        if not self._coordinator:
            return {
                "data": [],
                "url": None,
                "timestamp": None,
            }

        team_id = str(self._coordinator.team_id)
        response = await self.async_lookup_team(
            hass,
            team_id,
            self._get_api_key(),
            sensor_name,
        )

        payload = response.get("data")
        raw_teams = payload.get("teams") if isinstance(payload, dict) else None
        raw_team = (
            raw_teams[0]
            if isinstance(raw_teams, list) and raw_teams
            else None
        )

        if not isinstance(raw_team, dict):
            return {
                "data": [],
                "url": response.get("url"),
                "timestamp": response.get("timestamp"),
                "sportsdb_sport": "",
                "sportsdb_team": {},
            }

        team = self.team_to_standard(raw_team)

        return {
            "data": [team],
            "url": response.get("url"),
            "timestamp": response.get("timestamp"),
            "sportsdb_sport": str(raw_team.get("strSport") or ""),
            "sportsdb_team": raw_team,
        }

    async def _async_fetch_scoreboard_data(
        self,
        hass: HomeAssistant,
        lang: str,
    ) -> dict:
        """Fetch previous/next team events and convert to ESPN-like data."""
        del lang  # TheSportsDB v1 team schedule calls are not language-specific.

        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        sensor_name = self._coordinator.name
        sport_path = self._coordinator.sport_path
        league_path = self._coordinator.league_path
        team_id = str(self._coordinator.team_id)
        api_key = self._get_api_key()

        team_response = await self.async_get_team_data(
            hass,
            sport_path,
            league_path,
            sensor_name,
        )

        team_list = team_response.get("data") or []
        raw_team = team_response.get("sportsdb_team") or {}
        sportsdb_sport = str(team_response.get("sportsdb_sport") or "")

        self.lookups["team_list"] = team_list
        self.lookups["sportsdb_sport"] = sportsdb_sport

        if not team_list or not isinstance(raw_team, dict):
            return {
                "data": {"leagues": [], "events": []},
                "lookups": self.lookups,
                "url": team_response.get("url"),
                "timestamp": team_response.get("timestamp"),
            }

        previous_response = await self.async_call_sportsdb_api(
            hass,
            "eventslast.php",
            {"id": team_id},
            sensor_name,
            api_key=api_key,
        )
        next_response = await self.async_call_sportsdb_api(
            hass,
            "eventsnext.php",
            {"id": team_id},
            sensor_name,
            api_key=api_key,
        )

        source_events = self._extract_events(previous_response.get("data"))
        source_events.extend(
            self._extract_events(next_response.get("data"))
        )

        events_by_id: dict[str, dict] = {}

        for raw_event in source_events:
            if not isinstance(raw_event, dict):
                continue

            if team_id not in {
                str(raw_event.get("idHomeTeam") or ""),
                str(raw_event.get("idAwayTeam") or ""),
            }:
                continue

            event = self._build_espn_event(raw_event, raw_team)
            if event is None:
                continue

            event_id = str(event.get("id") or "")
            if event_id:
                events_by_id.setdefault(event_id, event)

        events = list(events_by_id.values())
        events.sort(key=lambda event: str(event.get("date") or ""))

        leagues_by_id: dict[str, dict] = {}
        for raw_event in source_events:
            if not isinstance(raw_event, dict):
                continue
            league_id = str(raw_event.get("idLeague") or "")
            if not league_id:
                continue
            leagues_by_id.setdefault(
                league_id,
                {
                    "id": league_id,
                    "abbreviation": str(raw_event.get("strLeague") or ""),
                    "name": str(raw_event.get("strLeague") or ""),
                    "logos": [
                        {
                            "href": str(
                                raw_event.get("strLeagueBadge") or ""
                            )
                        }
                    ],
                },
            )

        if not leagues_by_id:
            primary_league_id = str(raw_team.get("idLeague") or "")
            primary_league_name = str(raw_team.get("strLeague") or "")
            if primary_league_id:
                leagues_by_id[primary_league_id] = {
                    "id": primary_league_id,
                    "abbreviation": primary_league_name,
                    "name": primary_league_name,
                    "logos": [],
                }

        timestamp = (
            next_response.get("timestamp")
            or previous_response.get("timestamp")
            or team_response.get("timestamp")
        )

        # Never expose the V1 API key through the sensor api_url attribute.
        url = (
            next_response.get("url")
            or previous_response.get("url")
            or team_response.get("url")
        )

        return {
            "data": {
                "leagues": list(leagues_by_id.values()),
                "events": events,
            },
            "lookups": self.lookups,
            "url": url,
            "timestamp": timestamp,
        }

    @staticmethod
    def _extract_events(payload: Any) -> list[dict]:
        """Extract events from either v1 team schedule response shape."""
        if not isinstance(payload, dict):
            return []

        for key in ("events", "results"):
            events = payload.get(key)
            if isinstance(events, list):
                return events

        return []

    @staticmethod
    def team_to_standard(team: dict) -> dict:
        """Convert a TheSportsDB team into TeamTracker team-list format."""
        display_name = str(team.get("strTeam") or "")
        abbreviation = str(
            team.get("strTeamShort")
            or team.get("strTeamAlternate")
            or display_name
        )

        location = str(
            team.get("strStadiumLocation")
            or team.get("strLocation")
            or team.get("strCountry")
            or ""
        )

        return {
            "id": str(team.get("idTeam") or ""),
            "abbreviation": abbreviation,
            "displayName": display_name,
            "location": location,
        }

    def _build_espn_event(
        self,
        event: dict,
        configured_team: dict,
    ) -> dict | None:
        """Convert one TheSportsDB event into TeamTracker ESPN-like format."""
        event_id = str(event.get("idEvent") or "")
        event_date = self._event_date(event)
        if not event_id or not event_date:
            return None

        state = self._event_state(event)
        raw_status = str(event.get("strStatus") or "").strip()
        short_detail = raw_status or (
            "Final" if state == "post" else "Scheduled"
        )

        home = self._build_competitor(
            event,
            side="Home",
            home_away="home",
            configured_team=configured_team,
        )
        away = self._build_competitor(
            event,
            side="Away",
            home_away="away",
            configured_team=configured_team,
        )

        if state == "post":
            home_score = self._score_as_number(home.get("score"))
            away_score = self._score_as_number(away.get("score"))
            if home_score is not None and away_score is not None:
                home["winner"] = home_score > away_score
                away["winner"] = away_score > home_score

        status = {
            "clock": 0,
            "period": 0,
            "type": {
                "state": state,
                "completed": state == "post",
                "shortDetail": short_detail,
                "detail": short_detail,
            },
        }

        league_name = str(event.get("strLeague") or "")
        league_logo = str(event.get("strLeagueBadge") or "")
        league_id = str(event.get("idLeague") or "")

        venue = {
            "fullName": str(event.get("strVenue") or ""),
            "address": {
                "country": str(event.get("strCountry") or ""),
            },
        }

        short_name = str(
            event.get("strEventAlternate")
            or event.get("strEvent")
            or (
                f'{event.get("strAwayTeam", "")} @ '
                f'{event.get("strHomeTeam", "")}'
            )
        )

        result: dict[str, Any] = {
            "id": event_id,
            "date": event_date,
            "name": str(event.get("strEvent") or short_name),
            "shortName": short_name,
            "season": {
                "slug": self._slug(str(event.get("strSeason") or "")),
            },
            "status": status,
            "competitions": [
                {
                    "id": event_id,
                    "date": event_date,
                    "altGameNote": league_name,
                    "leagueId": league_id,
                    "leagueLogo": league_logo,
                    "venue": venue,
                    "competitors": [home, away],
                    "status": status,
                    "odds": [],
                }
            ],
        }

        video = str(event.get("strVideo") or "").strip()
        if video:
            result["links"] = [{"href": video}]

        return result

    def _build_competitor(
        self,
        event: dict,
        side: str,
        home_away: str,
        configured_team: dict,
    ) -> dict:
        """Build one ESPN-like competitor."""
        team_id = str(event.get(f"id{side}Team") or "")
        display_name = str(event.get(f"str{side}Team") or "")
        badge = str(event.get(f"str{side}TeamBadge") or "")

        is_configured = (
            team_id != ""
            and team_id == str(configured_team.get("idTeam") or "")
        )

        abbreviation = display_name
        color = "D3D3D3"
        alternate_color = "A9A9A9"

        if is_configured:
            abbreviation = str(
                configured_team.get("strTeamShort")
                or configured_team.get("strTeamAlternate")
                or display_name
            )
            color = self._normalize_color(
                configured_team.get("strColour1"),
                "D3D3D3",
            )
            alternate_color = self._normalize_color(
                configured_team.get("strColour2"),
                "A9A9A9",
            )

        score = event.get(f"int{side}Score")
        score_value = None if score is None else str(score)

        return {
            "id": team_id,
            "type": "team",
            "order": 0 if home_away == "home" else 1,
            "homeAway": home_away,
            "winner": None,
            "score": score_value,
            "team": {
                "id": team_id,
                "abbreviation": abbreviation,
                "displayName": display_name,
                "shortDisplayName": abbreviation,
                "logo": badge,
                "color": color,
                "alternateColor": alternate_color,
            },
            "records": [],
            "statistics": [],
        }

    def _event_state(self, event: dict) -> str:
        """Map provider-specific multi-sport status to PRE/IN/POST."""
        postponed = str(event.get("strPostponed") or "").strip().lower()
        if postponed in {"1", "true", "yes", "y"}:
            return "pre"

        status = str(event.get("strStatus") or "").strip()
        code = status.upper()

        pre_codes = {
            "NS",
            "TBD",
            "PST",
            "POST",  # Baseball/basketball/hockey/etc: postponed.
        }
        post_codes = {
            "FT",
            "AET",
            "PEN",
            "AOT",
            "AP",
            "AW",
            "AWD",
            "WO",
        }
        terminal_codes = {
            "CANC",
            "CANCELLED",
            "CANCELED",
            "ABD",
            "ABANDONED",
        }

        if code in pre_codes:
            return "pre"
        if code in post_codes:
            return "post"

        dt = self._event_datetime(event)

        if code in terminal_codes:
            if dt is not None and dt > datetime.now(timezone.utc):
                return "pre"
            return "post"

        upper_text = status.upper()

        if (
            "NOT START" in upper_text
            or "TIME TO BE DEFINED" in upper_text
            or "POSTPON" in upper_text
        ):
            return "pre"

        if (
            "FINISH" in upper_text
            or upper_text.startswith("FINAL")
            or "AFTER EXTRA" in upper_text
            or "AFTER PENALT" in upper_text
        ):
            return "post"

        # Any other explicit status is treated as an in-progress provider
        # state. This preserves provider-specific periods/sets/innings without
        # limiting the implementation to soccer.
        if status:
            return "in"

        home_score = event.get("intHomeScore")
        away_score = event.get("intAwayScore")
        if (
            dt is not None
            and dt <= datetime.now(timezone.utc)
            and home_score is not None
            and away_score is not None
        ):
            return "post"

        return "pre"

    def _event_date(self, event: dict) -> str:
        """Return UTC event timestamp in ESPN-compatible format."""
        dt = self._event_datetime(event)
        if dt is None:
            return ""
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    @staticmethod
    def _event_datetime(event: dict) -> datetime | None:
        """Parse TheSportsDB UTC timestamp/date fields."""
        timestamp = str(event.get("strTimestamp") or "").strip()

        if not timestamp:
            date_event = str(event.get("dateEvent") or "").strip()
            time_event = str(event.get("strTime") or "00:00:00").strip()
            if not date_event:
                return None
            timestamp = f"{date_event}T{time_event or '00:00:00'}"

        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

        # TheSportsDB documents its API timestamps in UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    @staticmethod
    def _score_as_number(value: Any) -> float | None:
        """Convert score to a numeric value where possible."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_color(value: Any, default: str) -> str:
        """Normalize provider color to ESPN's six-character hex style."""
        raw = str(value or "").strip().lstrip("#")
        if re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
            return raw.upper()
        return default

    @staticmethod
    def _slug(value: str) -> str:
        """Return a simple ESPN-like slug."""
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    async def async_call_sportsdb_api(
        self,
        hass: HomeAssistant,
        endpoint: str,
        params: dict | None,
        sensor_name: str,
        api_key: str | None = None,
    ) -> dict:
        """Call TheSportsDB V1 API without leaking the key to logs/state."""
        key = str(api_key or self._get_api_key()).strip().strip("/")
        key = key or SPORTSDB_FREE_API_KEY

        raw_base = f"{SPORTSDB_BASE_URL}/{key}/{endpoint}"
        safe_base = f"{SPORTSDB_BASE_URL}/***/{endpoint}"

        raw_url = str(URL(raw_base).with_query(params or {}))
        safe_url = str(URL(safe_base).with_query(params or {}))
        timestamp = arrow.now().format(arrow.FORMAT_W3C)

        _LOGGER.debug(
            "%s: Calling TheSportsDB API: %s",
            sensor_name,
            safe_url,
        )

        session = async_get_clientsession(hass)

        try:
            async with session.get(
                raw_url,
                headers={"Accept": "application/json"},
            ) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "%s: TheSportsDB API returned HTTP %s: %s",
                        sensor_name,
                        response.status,
                        safe_url,
                    )
                    return {
                        "data": None,
                        "url": safe_url,
                        "timestamp": timestamp,
                    }

                try:
                    data = await response.json(content_type=None)
                except (ValueError, json.JSONDecodeError):
                    _LOGGER.debug(
                        "%s: TheSportsDB returned non-JSON data",
                        sensor_name,
                    )
                    return {
                        "data": None,
                        "url": safe_url,
                        "timestamp": timestamp,
                    }

        except (aiohttp.ClientError, TimeoutError) as err:
            # Do not stringify the exception: aiohttp errors can contain the
            # requested URL, and V1 authenticates with the API key in its path.
            _LOGGER.debug(
                "%s: TheSportsDB API request failed (%s)",
                sensor_name,
                type(err).__name__,
            )
            return {
                "data": None,
                "url": safe_url,
                "timestamp": timestamp,
            }

        return {
            "data": data,
            "url": safe_url,
            "timestamp": timestamp,
        }
