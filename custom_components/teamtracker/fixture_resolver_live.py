"""Live-state extension for supplemental soccer fixtures."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_SPORTSDB_API_KEY, DOMAIN
from .fixture_resolver import (
    CONF_API_FOOTBALL_API_KEY,
    CONF_OPENFOOT_API_KEY,
    EMPTY_CACHE_TTL,
    FIXTURE_CACHE_TTL,
    SPORTSDB_BASE_URL,
    SPORTSDB_FREE_API_KEY,
    SoccerFixtureResolver,
    candidate_to_espn_event,
    dedupe_candidates,
    normalize_name,
    parse_datetime,
)

LIVE_CACHE_TTL = timedelta(seconds=30)
NEAR_KICKOFF_CACHE_TTL = timedelta(minutes=2)
LIVE_LOOKUP_PAST = timedelta(hours=6)
LIVE_LOOKUP_FUTURE = timedelta(hours=2)


def sportsdb_event_state(event: dict[str, Any]) -> str:
    """Map TheSportsDB event status to Team Tracker PRE/IN/POST."""
    postponed = str(event.get("strPostponed") or "").strip().lower()
    if postponed in {"1", "true", "yes", "y"}:
        return "pre"

    status = str(event.get("strStatus") or "").strip()
    code = status.upper()

    if code in {"NS", "TBD", "PST", "POST"}:
        return "pre"
    if code in {"FT", "AET", "PEN", "AOT", "AP", "AW", "AWD", "WO"}:
        return "post"
    if code in {"CANC", "CANCELLED", "CANCELED", "ABD", "ABANDONED"}:
        kickoff = parse_datetime(event.get("strTimestamp"))
        if kickoff is not None and kickoff > datetime.now(timezone.utc):
            return "pre"
        return "post"

    upper = status.upper()
    if (
        "NOT START" in upper
        or "TIME TO BE DEFINED" in upper
        or "POSTPON" in upper
    ):
        return "pre"
    if (
        "FINISH" in upper
        or upper.startswith("FINAL")
        or "AFTER EXTRA" in upper
        or "AFTER PENALT" in upper
    ):
        return "post"

    # Provider period/status values such as 1H, HT and 2H mean in progress.
    if status:
        return "in"
    return "pre"


def _score_number(value: Any) -> float | None:
    """Return a numeric score when possible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def candidate_to_live_espn_event(
    candidate: dict[str, Any],
    *,
    espn_team_id: str,
    team_name: str,
    team_logo: str = "",
) -> dict[str, Any]:
    """Convert a candidate while preserving supplemental live score/status."""
    event = candidate_to_espn_event(
        candidate,
        espn_team_id=espn_team_id,
        team_name=team_name,
        team_logo=team_logo,
    )

    state = str(candidate.get("state") or "pre").lower()
    detail = str(candidate.get("status_detail") or "").strip()
    if not detail:
        detail = "Final" if state == "post" else "Scheduled"

    status = {
        "clock": 0,
        "period": 0,
        "type": {
            "state": state,
            "completed": state == "post",
            "shortDetail": detail,
            "detail": detail,
        },
    }
    event["status"] = status

    competition = event["competitions"][0]
    competition["status"] = status
    competitors = competition.get("competitors") or []

    home_score = candidate.get("home_score")
    away_score = candidate.get("away_score")
    if len(competitors) >= 2:
        if home_score is not None:
            competitors[0]["score"] = str(home_score)
        if away_score is not None:
            competitors[1]["score"] = str(away_score)

        if state == "post":
            home_number = _score_number(home_score)
            away_number = _score_number(away_score)
            if home_number is not None and away_number is not None:
                competitors[0]["winner"] = home_number > away_number
                competitors[1]["winner"] = away_number > home_number

    return event


class LiveSoccerFixtureResolver(SoccerFixtureResolver):
    """Refresh supplemented fixtures quickly around kickoff and while live."""

    @staticmethod
    def _cache_ttl(events: list[dict[str, Any]], now: datetime) -> timedelta:
        if not events:
            return EMPTY_CACHE_TTL

        states = {
            str((event.get("status") or {}).get("type", {}).get("state") or "").lower()
            for event in events
            if isinstance(event, dict)
        }
        if "in" in states:
            return LIVE_CACHE_TTL

        for event in events:
            if not isinstance(event, dict):
                continue
            kickoff = parse_datetime(event.get("date"))
            if kickoff is None:
                continue
            delta = kickoff - now
            if -timedelta(hours=3) <= delta <= timedelta(hours=2):
                return NEAR_KICKOFF_CACHE_TTL

        return FIXTURE_CACHE_TTL

    async def _sportsdb_live_candidates(
        self,
        *,
        espn_team_id: str,
        team_name: str,
        api_key: str,
    ) -> list[dict[str, Any]]:
        """Enrich near-kickoff SportsDB fixtures from the free event lookup."""
        candidates = await super()._sportsdb_candidates(
            espn_team_id=espn_team_id,
            team_name=team_name,
            api_key=api_key,
        )
        if not candidates:
            return []

        key = api_key or SPORTSDB_FREE_API_KEY
        now = datetime.now(timezone.utc)
        result: list[dict[str, Any]] = []

        for candidate in candidates:
            enriched = dict(candidate)
            kickoff = candidate.get("kickoff")
            event_id = str(candidate.get("id") or "").strip()

            should_lookup = (
                event_id != ""
                and isinstance(kickoff, datetime)
                and now - LIVE_LOOKUP_PAST <= kickoff <= now + LIVE_LOOKUP_FUTURE
            )
            if should_lookup:
                payload = await self._json_get(
                    f"{SPORTSDB_BASE_URL}/{key}/lookupevent.php",
                    params={"id": event_id},
                )
                raw_events = (payload or {}).get("events") or []
                raw = next(
                    (
                        item
                        for item in raw_events
                        if isinstance(item, dict)
                        and str(item.get("idEvent") or "") == event_id
                    ),
                    None,
                )
                if isinstance(raw, dict):
                    enriched.update(
                        {
                            "state": sportsdb_event_state(raw),
                            "status_detail": str(raw.get("strStatus") or ""),
                            "home_score": raw.get("intHomeScore"),
                            "away_score": raw.get("intAwayScore"),
                        }
                    )

            result.append(enriched)

        return result

    async def async_resolve_events(
        self,
        *,
        coordinator: Any,
        espn_team_id: str,
        team_name: str,
        team_logo: str = "",
    ) -> list[dict[str, Any]]:
        """Return supplemental events with live state and live-aware caching."""
        if not espn_team_id or not team_name:
            return []

        await self._async_load()
        cache_key = f"{espn_team_id}:{normalize_name(team_name)}"
        now = datetime.now(timezone.utc)
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("cached_at"), datetime):
            cached_events = list(cached.get("events") or [])
            if now - cached["cached_at"] < self._cache_ttl(cached_events, now):
                return cached_events

        sportsdb_key = self._config_value(
            coordinator,
            CONF_SPORTSDB_API_KEY,
            SPORTSDB_FREE_API_KEY,
        )
        openfoot_key = self._config_value(coordinator, CONF_OPENFOOT_API_KEY)
        api_football_key = self._config_value(
            coordinator,
            CONF_API_FOOTBALL_API_KEY,
        )

        coroutines = [
            self._sportsdb_live_candidates(
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
                continue
            if isinstance(result, list):
                candidates.extend(result)

        candidates = [
            item
            for item in candidates
            if isinstance(item.get("kickoff"), datetime)
            and (
                str(item.get("state") or "").lower() in {"in", "post"}
                or item["kickoff"] >= now - timedelta(minutes=30)
            )
        ]
        candidates = dedupe_candidates(candidates)[:10]
        events = [
            candidate_to_live_espn_event(
                candidate,
                espn_team_id=espn_team_id,
                team_name=team_name,
                team_logo=team_logo,
            )
            for candidate in candidates
        ]
        self._cache[cache_key] = {"cached_at": now, "events": events}
        return events


async def async_get_live_fixture_resolver(
    hass: HomeAssistant,
) -> LiveSoccerFixtureResolver:
    """Return one live resolver shared by all Team Tracker sensors."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    resolver = domain_data.get("fixture_resolver_live")
    if not isinstance(resolver, LiveSoccerFixtureResolver):
        resolver = LiveSoccerFixtureResolver(hass)
        domain_data["fixture_resolver_live"] = resolver
    await resolver._async_load()  # pylint: disable=protected-access
    return resolver
