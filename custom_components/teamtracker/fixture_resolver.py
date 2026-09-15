"""Resolve missing soccer fixtures from supplemental free schedule sources."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import logging
import re
from typing import Any
import unicodedata

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import CONF_SPORTSDB_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

SPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"
OPENFOOT_BASE_URL = "https://openfootapi.com/v1"
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
SPORTSDB_FREE_API_KEY = "123"

CONF_OPENFOOT_API_KEY = "openfoot_api_key"
CONF_API_FOOTBALL_API_KEY = "api_football_api_key"

STORE_VERSION = 1
STORE_KEY = "teamtracker.fixture_resolver"
FIXTURE_CACHE_TTL = timedelta(hours=6)
EMPTY_CACHE_TTL = timedelta(hours=1)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=12)
SOURCE_PRIORITY = {
    "sportsdb": 0,
    "openfoot": 1,
    "api-football": 2,
}


def normalize_name(value: Any) -> str:
    """Normalize a team name for conservative cross-provider matching."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return " ".join(text.split())


def name_score(left: str, right: str) -> float:
    """Return a conservative similarity score for two team names."""
    a = normalize_name(left)
    b = normalize_name(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    a_tokens = set(a.split())
    b_tokens = set(b.split())
    subset_score = 0.95 if a_tokens <= b_tokens or b_tokens <= a_tokens else 0.0
    return max(SequenceMatcher(None, a, b).ratio(), subset_score)


def parse_datetime(value: Any) -> datetime | None:
    """Parse an API timestamp as aware UTC datetime."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _candidate_equivalent(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return True when two provider candidates describe the same fixture."""
    left_time = left.get("kickoff")
    right_time = right.get("kickoff")
    if not isinstance(left_time, datetime) or not isinstance(right_time, datetime):
        return False
    if abs((left_time - right_time).total_seconds()) > 15 * 60:
        return False

    return (
        name_score(str(left.get("home_name") or ""), str(right.get("home_name") or "")) >= 0.78
        and name_score(str(left.get("away_name") or ""), str(right.get("away_name") or "")) >= 0.78
    )


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate candidates across providers while preserving best source."""
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.get("kickoff") or datetime.max.replace(tzinfo=timezone.utc),
            SOURCE_PRIORITY.get(str(item.get("source") or ""), 99),
        ),
    )
    unique: list[dict[str, Any]] = []
    for candidate in ordered:
        if any(_candidate_equivalent(candidate, existing) for existing in unique):
            continue
        unique.append(candidate)
    return unique


def candidate_to_espn_event(
    candidate: dict[str, Any],
    *,
    espn_team_id: str,
    team_name: str,
    team_logo: str = "",
) -> dict[str, Any]:
    """Convert a supplemental fixture into the ESPN-like parser shape."""
    tracked_home = bool(candidate.get("tracked_home"))
    source = str(candidate.get("source") or "supplemental")
    kickoff = candidate["kickoff"].astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )

    home_name = team_name if tracked_home else str(candidate.get("home_name") or "")
    away_name = team_name if not tracked_home else str(candidate.get("away_name") or "")
    home_id = (
        espn_team_id
        if tracked_home
        else f"{source}:{candidate.get('home_id') or normalize_name(home_name)}"
    )
    away_id = (
        espn_team_id
        if not tracked_home
        else f"{source}:{candidate.get('away_id') or normalize_name(away_name)}"
    )
    home_logo = team_logo if tracked_home and team_logo else str(candidate.get("home_logo") or "")
    away_logo = team_logo if not tracked_home and team_logo else str(candidate.get("away_logo") or "")
    competition = str(candidate.get("competition") or "")
    league_id = str(candidate.get("league_id") or "")
    league_logo = str(candidate.get("league_logo") or "")
    event_id = f"{source}:{candidate.get('id') or kickoff}"

    status = {
        "clock": 0,
        "period": 0,
        "type": {
            "state": "pre",
            "completed": False,
            "shortDetail": "Scheduled",
            "detail": "Scheduled",
        },
    }

    def competitor(team_id: str, name: str, logo: str, home_away: str) -> dict[str, Any]:
        return {
            "id": team_id,
            "type": "team",
            "homeAway": home_away,
            "winner": False,
            "score": "0",
            "team": {
                "id": team_id,
                "abbreviation": name,
                "displayName": name,
                "shortDisplayName": name,
                "logo": logo,
                "color": "D3D3D3",
                "alternateColor": "A9A9A9",
            },
            "records": [],
            "statistics": [],
        }

    return {
        "id": event_id,
        "date": kickoff,
        "name": f"{away_name} at {home_name}",
        "shortName": f"{away_name} @ {home_name}",
        "season": {
            "displayName": competition,
            "slug": "",
        },
        "status": status,
        "_teamtracker_fixture_source": source,
        "competitions": [
            {
                "id": event_id,
                "date": kickoff,
                "altGameNote": competition,
                "leagueId": league_id,
                "leagueLogo": league_logo,
                "venue": {
                    "fullName": str(candidate.get("venue") or ""),
                    "address": {},
                },
                "competitors": [
                    competitor(home_id, home_name, home_logo, "home"),
                    competitor(away_id, away_name, away_logo, "away"),
                ],
                "status": status,
                "odds": [],
            }
        ],
    }


class SoccerFixtureResolver:
    """Resolve missing soccer fixtures without making ESPN depend on one source."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self._store = Store(hass, STORE_VERSION, STORE_KEY)
        self._mappings: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()

    async def _async_load(self) -> None:
        """Load persisted provider team mappings once."""
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            try:
                data = await self._store.async_load()
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.debug("Could not load fixture resolver mappings: %s", err)
                data = None
            if isinstance(data, dict) and isinstance(data.get("mappings"), dict):
                self._mappings = data["mappings"]
            self._loaded = True

    async def _async_save(self) -> None:
        """Persist only provider ID mappings, never API keys or fixture payloads."""
        try:
            await self._store.async_save({"mappings": self._mappings})
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Could not save fixture resolver mappings: %s", err)

    @staticmethod
    def _config_value(coordinator: Any, key: str, default: str = "") -> str:
        """Read an optional source key from entry options then entry data."""
        if coordinator is None:
            return default
        entry = getattr(coordinator, "entry", None)
        if entry is not None and getattr(entry, "options", None):
            value = entry.options.get(key)
            if value:
                return str(value).strip()
        config = getattr(coordinator, "config", None)
        if isinstance(config, dict):
            value = config.get(key)
            if value:
                return str(value).strip()
        return default

    async def _json_get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """Fetch JSON while isolating source failures from Team Tracker updates."""
        try:
            async with self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status != 200:
                    _LOGGER.debug("Fixture resolver HTTP %s from %s", response.status, url)
                    return None
                payload = await response.json(content_type=None)
                return payload if isinstance(payload, dict) else None
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Fixture resolver request failed for %s: %s", url, err)
            return None

    def _mapping_key(self, source: str, espn_team_id: str, team_name: str) -> str:
        return f"{source}:{espn_team_id}:{normalize_name(team_name)}"

    async def _mapped_team(
        self,
        source: str,
        espn_team_id: str,
        team_name: str,
        searcher,
    ) -> dict[str, str] | None:
        """Resolve and persist a provider-specific team ID."""
        await self._async_load()
        key = self._mapping_key(source, espn_team_id, team_name)
        cached = self._mappings.get(key)
        if isinstance(cached, dict) and cached.get("id") and cached.get("name"):
            return {"id": str(cached["id"]), "name": str(cached["name"])}

        choices = await searcher()
        if not isinstance(choices, list):
            return None

        best: dict[str, str] | None = None
        best_score = 0.0
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            provider_id = str(choice.get("id") or "").strip()
            provider_name = str(choice.get("name") or "").strip()
            if not provider_id or not provider_name:
                continue
            score = name_score(team_name, provider_name)
            if score > best_score:
                best_score = score
                best = {"id": provider_id, "name": provider_name}

        if best is None or best_score < 0.72:
            return None

        self._mappings[key] = best
        await self._async_save()
        return best

    async def _sportsdb_candidates(
        self,
        *,
        espn_team_id: str,
        team_name: str,
        api_key: str,
    ) -> list[dict[str, Any]]:
        """Return free TheSportsDB upcoming team fixtures."""
        key = api_key or SPORTSDB_FREE_API_KEY

        async def searcher() -> list[dict[str, str]]:
            payload = await self._json_get(
                f"{SPORTSDB_BASE_URL}/{key}/searchteams.php",
                params={"t": team_name},
            )
            return [
                {"id": str(team.get("idTeam") or ""), "name": str(team.get("strTeam") or "")}
                for team in (payload or {}).get("teams") or []
                if isinstance(team, dict)
            ]

        mapped = await self._mapped_team("sportsdb", espn_team_id, team_name, searcher)
        if not mapped:
            return []

        payload = await self._json_get(
            f"{SPORTSDB_BASE_URL}/{key}/eventsnext.php",
            params={"id": mapped["id"]},
        )
        events = []
        if isinstance(payload, dict):
            events = payload.get("events") or payload.get("results") or []

        result: list[dict[str, Any]] = []
        for raw in events:
            if not isinstance(raw, dict):
                continue
            kickoff = parse_datetime(raw.get("strTimestamp"))
            if kickoff is None:
                date_value = str(raw.get("dateEvent") or "").strip()
                time_value = str(raw.get("strTime") or "00:00:00").strip()
                if date_value:
                    kickoff = parse_datetime(f"{date_value}T{time_value}+00:00")
            if kickoff is None:
                continue

            home_id = str(raw.get("idHomeTeam") or "")
            away_id = str(raw.get("idAwayTeam") or "")
            tracked_home = home_id == mapped["id"]
            tracked_away = away_id == mapped["id"]
            if not tracked_home and not tracked_away:
                continue

            result.append(
                {
                    "source": "sportsdb",
                    "id": str(raw.get("idEvent") or ""),
                    "kickoff": kickoff,
                    "competition": str(raw.get("strLeague") or ""),
                    "league_id": str(raw.get("idLeague") or ""),
                    "league_logo": str(raw.get("strLeagueBadge") or ""),
                    "home_id": home_id,
                    "home_name": str(raw.get("strHomeTeam") or ""),
                    "home_logo": str(raw.get("strHomeTeamBadge") or ""),
                    "away_id": away_id,
                    "away_name": str(raw.get("strAwayTeam") or ""),
                    "away_logo": str(raw.get("strAwayTeamBadge") or ""),
                    "tracked_home": tracked_home,
                    "venue": str(raw.get("strVenue") or ""),
                }
            )
        return result

    async def _openfoot_candidates(
        self,
        *,
        espn_team_id: str,
        team_name: str,
        api_key: str,
    ) -> list[dict[str, Any]]:
        """Return OpenFoot fixtures when a free Starter key is configured."""
        if not api_key:
            return []
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

        async def searcher() -> list[dict[str, str]]:
            payload = await self._json_get(
                f"{OPENFOOT_BASE_URL}/search",
                params={"q": team_name},
                headers=headers,
            )
            choices = []
            for raw in (payload or {}).get("data") or []:
                if not isinstance(raw, dict):
                    continue
                team = raw.get("team") if isinstance(raw.get("team"), dict) else raw
                provider_id = str(team.get("id") or raw.get("id") or "")
                provider_name = str(team.get("name") or team.get("displayName") or raw.get("name") or "")
                kind = str(raw.get("type") or raw.get("entityType") or "").lower()
                if provider_id and provider_name and (not kind or "team" in kind or provider_id.startswith("team_")):
                    choices.append({"id": provider_id, "name": provider_name})
            return choices

        mapped = await self._mapped_team("openfoot", espn_team_id, team_name, searcher)
        if not mapped:
            return []

        payload = await self._json_get(
            f"{OPENFOOT_BASE_URL}/matches",
            params={"team": mapped["id"], "status": "scheduled"},
            headers=headers,
        )
        result: list[dict[str, Any]] = []
        for raw in (payload or {}).get("data") or []:
            if not isinstance(raw, dict):
                continue
            kickoff = parse_datetime(raw.get("kickoffAt") or raw.get("date"))
            if kickoff is None:
                continue
            home = raw.get("homeTeam") if isinstance(raw.get("homeTeam"), dict) else {}
            away = raw.get("awayTeam") if isinstance(raw.get("awayTeam"), dict) else {}
            home_id = str(home.get("id") or "")
            away_id = str(away.get("id") or "")
            home_name = str(home.get("name") or home.get("displayName") or "")
            away_name = str(away.get("name") or away.get("displayName") or "")
            tracked_home = home_id == mapped["id"] or name_score(home_name, team_name) >= 0.85
            tracked_away = away_id == mapped["id"] or name_score(away_name, team_name) >= 0.85
            if not tracked_home and not tracked_away:
                continue
            competition = raw.get("competition") if isinstance(raw.get("competition"), dict) else {}
            venue_raw = raw.get("venue")
            venue = str(venue_raw.get("name") or "") if isinstance(venue_raw, dict) else str(venue_raw or "")
            result.append(
                {
                    "source": "openfoot",
                    "id": str(raw.get("id") or ""),
                    "kickoff": kickoff,
                    "competition": str(competition.get("name") or raw.get("competitionName") or raw.get("competitionId") or ""),
                    "league_id": str(competition.get("id") or raw.get("competitionId") or ""),
                    "league_logo": str(competition.get("logo") or ""),
                    "home_id": home_id,
                    "home_name": home_name,
                    "home_logo": str(home.get("logo") or home.get("badge") or ""),
                    "away_id": away_id,
                    "away_name": away_name,
                    "away_logo": str(away.get("logo") or away.get("badge") or ""),
                    "tracked_home": tracked_home,
                    "venue": venue,
                }
            )
        return result

    async def _api_football_candidates(
        self,
        *,
        espn_team_id: str,
        team_name: str,
        api_key: str,
    ) -> list[dict[str, Any]]:
        """Return API-Football fixtures when a free key is configured."""
        if not api_key:
            return []
        headers = {"x-apisports-key": api_key}

        async def searcher() -> list[dict[str, str]]:
            payload = await self._json_get(
                f"{API_FOOTBALL_BASE_URL}/teams",
                params={"search": team_name},
                headers=headers,
            )
            choices = []
            for raw in (payload or {}).get("response") or []:
                if not isinstance(raw, dict) or not isinstance(raw.get("team"), dict):
                    continue
                team = raw["team"]
                choices.append({"id": str(team.get("id") or ""), "name": str(team.get("name") or "")})
            return choices

        mapped = await self._mapped_team("api-football", espn_team_id, team_name, searcher)
        if not mapped:
            return []

        payload = await self._json_get(
            f"{API_FOOTBALL_BASE_URL}/fixtures",
            params={"team": mapped["id"], "next": 10},
            headers=headers,
        )
        result: list[dict[str, Any]] = []
        for raw in (payload or {}).get("response") or []:
            if not isinstance(raw, dict):
                continue
            fixture = raw.get("fixture") if isinstance(raw.get("fixture"), dict) else {}
            teams = raw.get("teams") if isinstance(raw.get("teams"), dict) else {}
            home = teams.get("home") if isinstance(teams.get("home"), dict) else {}
            away = teams.get("away") if isinstance(teams.get("away"), dict) else {}
            kickoff = parse_datetime(fixture.get("date"))
            if kickoff is None:
                continue
            home_id = str(home.get("id") or "")
            away_id = str(away.get("id") or "")
            tracked_home = home_id == mapped["id"]
            tracked_away = away_id == mapped["id"]
            if not tracked_home and not tracked_away:
                continue
            league = raw.get("league") if isinstance(raw.get("league"), dict) else {}
            venue = fixture.get("venue") if isinstance(fixture.get("venue"), dict) else {}
            result.append(
                {
                    "source": "api-football",
                    "id": str(fixture.get("id") or ""),
                    "kickoff": kickoff,
                    "competition": str(league.get("name") or ""),
                    "league_id": str(league.get("id") or ""),
                    "league_logo": str(league.get("logo") or ""),
                    "home_id": home_id,
                    "home_name": str(home.get("name") or ""),
                    "home_logo": str(home.get("logo") or ""),
                    "away_id": away_id,
                    "away_name": str(away.get("name") or ""),
                    "away_logo": str(away.get("logo") or ""),
                    "tracked_home": tracked_home,
                    "venue": str(venue.get("name") or ""),
                }
            )
        return result

    async def async_resolve_events(
        self,
        *,
        coordinator: Any,
        espn_team_id: str,
        team_name: str,
        team_logo: str = "",
    ) -> list[dict[str, Any]]:
        """Return upcoming supplemental events, never raising into the sensor update."""
        if not espn_team_id or not team_name:
            return []

        await self._async_load()
        cache_key = f"{espn_team_id}:{normalize_name(team_name)}"
        now = datetime.now(timezone.utc)
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("cached_at"), datetime):
            ttl = FIXTURE_CACHE_TTL if cached.get("events") else EMPTY_CACHE_TTL
            if now - cached["cached_at"] < ttl:
                return list(cached.get("events") or [])

        sportsdb_key = self._config_value(
            coordinator,
            CONF_SPORTSDB_API_KEY,
            SPORTSDB_FREE_API_KEY,
        )
        openfoot_key = self._config_value(coordinator, CONF_OPENFOOT_API_KEY)
        api_football_key = self._config_value(coordinator, CONF_API_FOOTBALL_API_KEY)

        coroutines = [
            self._sportsdb_candidates(
                espn_team_id=espn_team_id,
                team_name=team_name,
                api_key=sportsdb_key,
            )
        ]
        if openfoot_key:
            coroutines.append(
                self._openfoot_candidates(
                    espn_team_id=espn_team_id,
                    team_name=team_name,
                    api_key=openfoot_key,
                )
            )
        if api_football_key:
            coroutines.append(
                self._api_football_candidates(
                    espn_team_id=espn_team_id,
                    team_name=team_name,
                    api_key=api_football_key,
                )
            )

        gathered = await asyncio.gather(*coroutines, return_exceptions=True)
        candidates: list[dict[str, Any]] = []
        for result in gathered:
            if isinstance(result, Exception):
                _LOGGER.debug("Supplemental fixture source failed: %s", result)
                continue
            if isinstance(result, list):
                candidates.extend(result)

        candidates = [
            item
            for item in candidates
            if isinstance(item.get("kickoff"), datetime)
            and item["kickoff"] >= now - timedelta(minutes=30)
        ]
        candidates = dedupe_candidates(candidates)[:10]
        events = [
            candidate_to_espn_event(
                candidate,
                espn_team_id=espn_team_id,
                team_name=team_name,
                team_logo=team_logo,
            )
            for candidate in candidates
        ]
        self._cache[cache_key] = {"cached_at": now, "events": events}
        return events


async def async_get_fixture_resolver(hass: HomeAssistant) -> SoccerFixtureResolver:
    """Return one resolver instance shared by all Team Tracker sensors."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    resolver = domain_data.get("fixture_resolver")
    if not isinstance(resolver, SoccerFixtureResolver):
        resolver = SoccerFixtureResolver(hass)
        domain_data["fixture_resolver"] = resolver
    await resolver._async_load()  # pylint: disable=protected-access
    return resolver
