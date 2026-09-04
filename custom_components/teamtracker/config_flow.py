"""Guided universal config flow for Team Tracker."""

from __future__ import annotations

from copy import deepcopy

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import logging
import re
from typing import Any
import unicodedata
from urllib.parse import unquote

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.translation import async_get_translations

from .const import (
    CONF_API_LANGUAGE,
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TEAM_ID,
    DOMAIN,
    NATIVE_LEAGUES,
)
from .provider_factory import get_provider

_LOGGER = logging.getLogger(__name__)

ALL_COMPETITIONS = "__all__"
CUSTOM_SPORT = "custom_api"
CORE_BASE_URL = "https://sports.core.api.espn.com"
SITE_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
SEARCH_BASE_URL = "https://site.web.api.espn.com/apis/search/v2"

# Cricket stays available through Advanced / Custom API. The external API audit
# found no reliable ESPN league catalog for cricket and sport-filtered discovery
# leaked unrelated sports, so presenting it as a normal guided sport would make
# the flow look more reliable than ESPN's current data actually is.
SPORTS = (
    "australian-football",
    "baseball",
    "basketball",
    "football",
    "golf",
    "hockey",
    "mma",
    "racing",
    "rugby",
    "soccer",
    "tennis",
    "volleyball",
    CUSTOM_SPORT,
)

INDIVIDUAL_SPORTS = frozenset({"golf", "mma", "racing", "tennis"})

# These are resilience hints, not the authority. Every search merges the live
# ESPN league catalog, so newly added competitions can appear without a Team
# Tracker release.


def _pretty(value: str) -> str:
    """Humanize an ESPN slug."""
    return value.replace(".", " ").replace("-", " ").replace("_", " ").title()


def _dropdown(options: list[tuple[str, str]]) -> SelectSelector:
    """Return a Home Assistant dropdown with explicit dynamic labels."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=value, label=label) for value, label in options
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def competitor_id(competitor: dict[str, Any]) -> str:
    """Return the canonical ESPN competitor id when present."""
    direct = str(competitor.get("id") or "").strip()
    if direct.isdigit():
        return direct

    for key in ("team", "athlete", "roster"):
        nested = competitor.get(key)
        if not isinstance(nested, dict):
            continue
        value = str(nested.get("id") or "").strip()
        if value.isdigit():
            return value

    uid = str(competitor.get("uid") or "")
    match = re.search(r"(?:^|~)[ta]:(\d+)(?:~|$)", uid, re.IGNORECASE)
    return match.group(1) if match else ""

def competitor_names(competitor: dict[str, Any]) -> list[str]:
    """Return useful names/abbreviations for a competitor."""
    values: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in values:
            values.append(text)

    add(competitor.get("displayName"))
    add(competitor.get("name"))

    for key in ("team", "athlete", "roster"):
        nested = competitor.get(key)
        if not isinstance(nested, dict):
            continue
        add(nested.get("displayName"))
        add(nested.get("fullName"))
        add(nested.get("shortDisplayName"))
        add(nested.get("name"))
        add(nested.get("abbreviation"))

    return values

def competitor_matches(competitor: dict[str, Any], search_key: str) -> bool:
    """Match a configured Team Tracker competitor against an ESPN competitor."""
    key = str(search_key or "").strip()
    if not key:
        return False
    if key == "*":
        return True

    canonical_id = competitor_id(competitor)
    if key.isdigit() and canonical_id == key:
        return True

    key_upper = key.upper()
    for name in competitor_names(competitor):
        name_upper = name.upper()
        if key_upper == name_upper:
            return True
        try:
            if re.fullmatch(key_upper, name_upper):
                return True
        except re.error:
            # Invalid user regex should simply fail to match here; the parser
            # will report the normal configuration warning when it evaluates it.
            return False

        # Preserve Team Tracker's historical athlete-name behavior, where a
        # plain configured name may be a substring of the full athlete name.
        if competitor.get("type") == "athlete" and key_upper in name_upper:
            return True

    return False

def iter_competitions(event: dict[str, Any]) -> Iterable[tuple[dict[str, Any] | None, dict[str, Any]]]:
    """Yield (grouping, competition) pairs from either ESPN event layout."""
    groupings = event.get("groupings") or []
    if isinstance(groupings, list) and groupings:
        for grouping in groupings:
            if not isinstance(grouping, dict):
                continue
            for competition in grouping.get("competitions") or []:
                if isinstance(competition, dict):
                    yield grouping, competition
        return

    for competition in event.get("competitions") or []:
        if isinstance(competition, dict):
            yield None, competition

def competition_contains(competition: dict[str, Any], search_key: str) -> bool:
    """Return True when a competition contains the selected competitor."""
    return any(
        competitor_matches(competitor, search_key)
        for competitor in competition.get("competitors") or []
        if isinstance(competitor, dict)
    )

def _competition_key(event: dict[str, Any], competition: dict[str, Any]) -> str:
    """Return a stable deduplication key for a match/competition."""
    competition_id = str(competition.get("id") or "").strip()
    if competition_id:
        return f"competition:{competition_id}"

    uid = str(competition.get("uid") or "").strip()
    if uid:
        return f"uid:{uid}"

    event_id = str(event.get("id") or "").strip()
    date_value = str(competition.get("date") or event.get("date") or "")
    return f"fallback:{event_id}|{date_value}"

def filter_event_for_competitor(
    event: dict[str, Any],
    search_key: str,
    seen_competitions: set[str] | None = None,
) -> dict[str, Any] | None:
    """Return an ESPN event containing only matching, not-yet-seen competitions."""
    seen = seen_competitions if seen_competitions is not None else set()
    filtered = deepcopy(event)

    groupings = event.get("groupings") or []
    if isinstance(groupings, list) and groupings:
        kept_groupings: list[dict[str, Any]] = []
        for original_grouping in groupings:
            if not isinstance(original_grouping, dict):
                continue
            grouping = deepcopy(original_grouping)
            kept_competitions: list[dict[str, Any]] = []
            for competition in original_grouping.get("competitions") or []:
                if not isinstance(competition, dict):
                    continue
                key = _competition_key(event, competition)
                if key in seen or not competition_contains(competition, search_key):
                    continue
                seen.add(key)
                kept_competitions.append(deepcopy(competition))
            if kept_competitions:
                grouping["competitions"] = kept_competitions
                kept_groupings.append(grouping)

        if not kept_groupings:
            return None
        filtered["groupings"] = kept_groupings
        filtered.pop("competitions", None)
        return filtered

    kept_competitions = []
    for competition in event.get("competitions") or []:
        if not isinstance(competition, dict):
            continue
        key = _competition_key(event, competition)
        if key in seen or not competition_contains(competition, search_key):
            continue
        seen.add(key)
        kept_competitions.append(deepcopy(competition))

    if not kept_competitions:
        return None
    filtered["competitions"] = kept_competitions
    return filtered

def merge_matching_events(
    payloads: Iterable[dict[str, Any]],
    search_key: str,
) -> list[dict[str, Any]]:
    """Merge ESPN payloads, filtering and deduplicating by match id."""
    events: list[dict[str, Any]] = []
    seen: set[str] = set()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for event in payload.get("events") or []:
            if not isinstance(event, dict):
                continue
            filtered = filter_event_for_competitor(event, search_key, seen)
            if filtered is not None:
                events.append(filtered)

    return events

class TeamTrackerScoresFlowHandler(
    config_entries.ConfigFlow, domain=DOMAIN
):  # type: ignore[call-arg]
    """Configure Team Tracker as sport -> competitor -> competition."""

    VERSION = 3

    def __init__(self) -> None:
        self._sport_path = ""
        self._competitor_kind = "team"
        self._competitor_id = ""
        self._competitor_name = ""
        self._results: dict[str, dict[str, Any]] = {}
        self._competition_options: dict[str, str] = {}
        self._league_cache: dict[str, dict[str, str]] = {}
        self._http_cache: dict[str, dict | None] = {}
        self._athlete_pages: dict[tuple[str, str], list[dict]] = {}
        self._errors: dict[str, str] = {}

    # ------------------------------------------------------------------
    # HTTP and catalog helpers
    # ------------------------------------------------------------------

    async def _json(
        self, url: str, params: dict[str, str] | None = None
    ) -> dict | None:
        """Fetch JSON once per flow and return None for unsupported endpoints."""
        from yarl import URL

        key = str(URL(url).with_query(params))
        if key in self._http_cache:
            return self._http_cache[key]

        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    _LOGGER.debug("ESPN HTTP %s: %s", response.status, response.url)
                    self._http_cache[key] = None
                    return None
                payload = await response.json(content_type=None)
                result = payload if isinstance(payload, dict) else None
                self._http_cache[key] = result
                return result
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("ESPN discovery request failed for %s: %s", url, err)
            self._http_cache[key] = None
            return None

    async def _league_catalog(self) -> dict[str, str]:
        """Return the live ESPN league catalog merged with stable fallbacks."""
        if self._sport_path in self._league_cache:
            return self._league_cache[self._sport_path]

        catalog: dict[str, str] = {}

        for league_id, values in NATIVE_LEAGUES.items():
            if values.get(CONF_SPORT_PATH) != self._sport_path:
                continue
            path = str(values.get(CONF_LEAGUE_PATH) or "").strip()
            if path and path != "all":
                catalog.setdefault(path, league_id)

        payload = await self._json(
            f"{CORE_BASE_URL}/v2/sports/{self._sport_path}/leagues",
            {"limit": "1000"},
        )
        for item in (payload or {}).get("items") or []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("slug") or "").strip()
            ref = str(item.get("$ref") or "")
            if not path and ref:
                match = re.search(r"/leagues/([^/?#]+)", ref)
                if match:
                    path = unquote(match.group(1))
            if not path or path == "all":
                continue
            label = str(
                item.get("name")
                or item.get("shortName")
                or item.get("abbreviation")
                or ""
            ).strip()
            catalog.setdefault(path, label or _pretty(path))

        self._league_cache[self._sport_path] = catalog
        return catalog

    @staticmethod
    def _league_label(payload: dict, fallback: str) -> str:
        """Read a display label from a Site API response."""
        for sport in payload.get("sports") or []:
            if not isinstance(sport, dict):
                continue
            for league in sport.get("leagues") or []:
                if not isinstance(league, dict):
                    continue
                label = str(
                    league.get("name")
                    or league.get("shortName")
                    or league.get("abbreviation")
                    or ""
                ).strip()
                if label:
                    return label
        for league in payload.get("leagues") or []:
            if isinstance(league, dict):
                label = str(
                    league.get("name")
                    or league.get("shortName")
                    or league.get("abbreviation")
                    or ""
                ).strip()
                if label:
                    return label
        return fallback

    # ------------------------------------------------------------------
    # Search matching
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_search_text(value: Any) -> str:
        """Normalize case, accents and punctuation for human-name matching."""
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(
            character for character in text if not unicodedata.combining(character)
        )
        text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
        return " ".join(text.split())

    def _matches_search(self, query: str, candidate: str) -> bool:
        """Conservatively match spelling and common transliteration variants."""
        wanted = self._normalize_search_text(query)
        name = self._normalize_search_text(candidate)
        if not wanted or not name:
            return False
        if wanted in name:
            return True

        variants = {wanted}
        replacements = (
            ("k", "c"),
            ("c", "k"),
            ("ph", "f"),
            ("f", "ph"),
            ("y", "i"),
            ("i", "y"),
        )
        for old, new in replacements:
            if old in wanted:
                variants.add(wanted.replace(old, new))

        if any(variant and variant in name for variant in variants):
            return True

        if len(wanted) >= 4 and SequenceMatcher(None, wanted, name).ratio() >= 0.84:
            return True

        name_tokens = name.split()
        for wanted_token in wanted.split():
            if len(wanted_token) < 4:
                continue
            if any(
                len(token) >= 4
                and SequenceMatcher(None, wanted_token, token).ratio() >= 0.84
                for token in name_tokens
            ):
                return True
        return False

    def _match_rank(self, query: str, name: str) -> tuple[float, int, str]:
        """Sort the most canonical-looking name match first."""
        wanted = self._normalize_search_text(query)
        candidate = self._normalize_search_text(name)
        ratio = SequenceMatcher(None, wanted, candidate).ratio()
        exact_words = int(len(wanted.split()) != len(candidate.split()))
        return (-ratio, exact_words, candidate)

    # ------------------------------------------------------------------
    # Team discovery: actual sport league team collections only
    # ------------------------------------------------------------------

    @staticmethod
    def _teams_from_payload(payload: dict) -> list[dict[str, Any]]:
        """Extract canonical team records from a Site API teams response."""
        teams: dict[str, dict[str, Any]] = {}
        for sport in payload.get("sports") or []:
            if not isinstance(sport, dict):
                continue
            for league in sport.get("leagues") or []:
                if not isinstance(league, dict):
                    continue
                for wrapper in league.get("teams") or []:
                    if not isinstance(wrapper, dict):
                        continue
                    team = wrapper.get("team") if isinstance(wrapper.get("team"), dict) else wrapper
                    team_id = str(team.get("id") or "").strip()
                    name = str(team.get("displayName") or team.get("name") or "").strip()
                    if not team_id.isdigit() or not name:
                        continue
                    teams[team_id] = {
                        "id": team_id,
                        "kind": "team",
                        "displayName": name,
                        "abbreviation": str(team.get("abbreviation") or "").strip(),
                        "location": str(team.get("location") or "").strip(),
                        "competitions": {},
                    }
        return list(teams.values())

    @staticmethod
    def _event_candidates_from_payload(
        payload: dict,
        kind: str,
    ) -> list[dict[str, Any]]:
        """Extract canonical competitors directly from real ESPN events."""
        found: dict[str, dict[str, Any]] = {}

        for event in payload.get("events") or []:
            if not isinstance(event, dict):
                continue

            for _grouping, competition in iter_competitions(event):
                for competitor in competition.get("competitors") or []:
                    if not isinstance(competitor, dict):
                        continue

                    if kind == "team":
                        entity = competitor.get("team")
                        if not isinstance(entity, dict):
                            continue
                    else:
                        entity = competitor.get("athlete")

                        if not isinstance(entity, dict):
                            entity = competitor.get("driver")

                        if (
                            not isinstance(entity, dict)
                            and not isinstance(competitor.get("team"), dict)
                        ):
                            entity = competitor

                        if not isinstance(entity, dict):
                            continue

                    competitor_id = str(
                        entity.get("id")
                        or competitor.get("id")
                        or ""
                    ).strip()

                    name = str(
                        entity.get("displayName")
                        or entity.get("fullName")
                        or entity.get("shortName")
                        or entity.get("name")
                        or ""
                    ).strip()

                    if not competitor_id.isdigit() or not name:
                        continue

                    candidate = {
                        "id": competitor_id,
                        "kind": kind,
                        "displayName": name,
                        "location": str(
                            entity.get("location")
                            or ""
                        ).strip(),
                        "competitions": {},
                    }

                    if kind == "team":
                        candidate["abbreviation"] = str(
                            entity.get("abbreviation")
                            or ""
                        ).strip()
                    else:
                        candidate["description"] = str(
                            entity.get("description")
                            or ""
                        ).strip()

                    found.setdefault(
                        competitor_id,
                        candidate,
                    )

        return list(found.values())

    async def _event_discovery_payloads(
        self,
        league_path: str,
    ) -> list[dict]:
        """Fetch real event data when ESPN has no useful identity collection."""
        url = (
            f"{SITE_BASE_URL}/{self._sport_path}/"
            f"{league_path}/scoreboard"
        )

        current, broad = await asyncio.gather(
            self._json(
                url,
                {"limit": "1000"},
            ),
            self._json(
                url,
                {
                    "limit": "1000",
                    "dates": self._verification_dates(),
                },
            ),
        )

        payloads: list[dict] = []

        for payload in (current, broad):
            if (
                isinstance(payload, dict)
                and payload not in payloads
            ):
                payloads.append(payload)

        return payloads

    async def _search_team_sport(
        self,
        term: str,
    ) -> list[dict[str, Any]]:
        """Search canonical teams using collections with event fallback."""
        if self._sport_path == "soccer":
            paths = await self._async_soccer_all_league_paths()
            catalog = {path: path for path in paths}
        else:
            catalog = await self._league_catalog()
        semaphore = asyncio.Semaphore(12)

        async def search_league(
            league_path: str,
            fallback_label: str,
        ):
            async with semaphore:
                payload = await self._json(
                    (
                        f"{SITE_BASE_URL}/{self._sport_path}/"
                        f"{league_path}/teams"
                    ),
                    {"limit": "1000"},
                )

            teams = (
                self._teams_from_payload(payload)
                if payload
                else []
            )

            label = (
                self._league_label(
                    payload,
                    fallback_label,
                )
                if payload
                else fallback_label
            )

            # Some ESPN competitions expose valid events but no useful
            # /teams collection. In that case real event competitors are
            # the identity source.
            if not teams:
                async with semaphore:
                    event_payloads = await self._event_discovery_payloads(
                        league_path
                    )

                event_teams: dict[str, dict[str, Any]] = {}

                for event_payload in event_payloads:
                    label = self._league_label(
                        event_payload,
                        label,
                    )

                    for team in self._event_candidates_from_payload(
                        event_payload,
                        "team",
                    ):
                        event_teams.setdefault(
                            team["id"],
                            team,
                        )

                teams = list(
                    event_teams.values()
                )

            matches = [
                team
                for team in teams
                if (
                    self._matches_search(
                        term,
                        team["displayName"],
                    )
                    or self._matches_search(
                        term,
                        team.get("abbreviation", ""),
                    )
                    or self._matches_search(
                        term,
                        team.get("location", ""),
                    )
                    or term.strip() == team["id"]
                )
            ]

            return (
                league_path,
                label,
                matches,
            )

        responses = await asyncio.gather(
            *(
                search_league(
                    league_path,
                    label,
                )
                for league_path, label in catalog.items()
            )
        )

        found: dict[str, dict[str, Any]] = {}

        for league_path, label, teams in responses:
            for team in teams:
                team_id = team["id"]

                existing = found.setdefault(
                    team_id,
                    dict(team),
                )

                existing.setdefault(
                    "competitions",
                    {},
                )[league_path] = label

                if (
                    not existing.get("abbreviation")
                    and team.get("abbreviation")
                ):
                    existing["abbreviation"] = team["abbreviation"]

                if (
                    not existing.get("location")
                    and team.get("location")
                ):
                    existing["location"] = team["location"]

        return sorted(
            found.values(),
            key=lambda item: self._match_rank(
                term,
                item["displayName"],
            ),
        )

    # ------------------------------------------------------------------
    # Athlete identity discovery: collections are identity sources only
    # ------------------------------------------------------------------

    @staticmethod
    def _canonical_search_athlete_id(item: dict[str, Any]) -> str:
        """Extract the canonical numeric ESPN athlete ID from search content."""
        uid = str(item.get("uid") or "")
        match = re.search(r"(?:^|~)a:(\d+)(?:~|$)", uid)
        if match:
            return match.group(1)

        link = item.get("link") or {}
        web = str(link.get("web") if isinstance(link, dict) else "")
        for pattern in (
            r"/(?:player|fighter|driver)/_/id/(\d+)(?:/|$)",
            r"/(?:player|fighter|driver)/id/(\d+)(?:/|$)",
        ):
            match = re.search(pattern, web, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    async def _search_individual_candidates(
        self, term: str
    ) -> list[dict[str, Any]]:
        """Use ESPN search only as a sport-checked canonical identity source."""
        payload = await self._json(
            SEARCH_BASE_URL,
            {"query": term, "sport": self._sport_path, "limit": "100"},
        )
        found: dict[str, dict[str, Any]] = {}

        for group in (payload or {}).get("results") or []:
            if not isinstance(group, dict) or group.get("type") != "player":
                continue
            for item in group.get("contents") or []:
                if not isinstance(item, dict) or item.get("type") != "player":
                    continue
                # The API can leak players from other sports even when the
                # sport query parameter is supplied. Enforce the item's own
                # sport value before accepting its canonical identity.
                if str(item.get("sport") or "").casefold() != self._sport_path.casefold():
                    continue

                athlete_id = self._canonical_search_athlete_id(item)
                name = str(item.get("displayName") or "").strip()
                if (
                    not athlete_id
                    or not name
                    or (
                        not self._matches_search(term, name)
                        and term.strip() != athlete_id
                    )
                ):
                    continue

                found[athlete_id] = {
                    "id": athlete_id,
                    "kind": "athlete",
                    "displayName": name,
                    "location": "",
                    "description": str(item.get("description") or "").strip(),
                    "competitions": {},
                }

        # ESPN search results are already relevance-ranked. Preserve that
        # ordering after our strict sport/type/ID validation instead of
        # re-sorting same-surname athletes alphabetically or by name length.
        return list(found.values())

    async def _athlete_collection_pages(self, league_path: str) -> list[dict]:
        """Fetch every V3 athlete page for one sport/league collection."""
        cache_key = (self._sport_path, league_path)
        if cache_key in self._athlete_pages:
            return self._athlete_pages[cache_key]

        url = f"{CORE_BASE_URL}/v3/sports/{self._sport_path}/{league_path}/athletes"
        first = await self._json(url, {"limit": "1000", "page": "1"})
        if not first:
            self._athlete_pages[cache_key] = []
            return []

        try:
            page_count = max(1, min(int(first.get("pageCount") or 1), 100))
        except (TypeError, ValueError):
            page_count = 1

        pages = [first]
        if page_count > 1:
            semaphore = asyncio.Semaphore(6)

            async def fetch_page(page: int) -> tuple[int, dict | None]:
                async with semaphore:
                    return page, await self._json(
                        url, {"limit": "1000", "page": str(page)}
                    )

            responses = await asyncio.gather(
                *(fetch_page(page) for page in range(2, page_count + 1))
            )
            pages.extend(
                payload
                for _page, payload in sorted(responses)
                if isinstance(payload, dict)
            )

        self._athlete_pages[cache_key] = pages
        return pages

    @staticmethod
    def _athletes_from_pages(pages: list[dict]) -> list[dict[str, Any]]:
        """Extract actual top-level athlete objects, never nested event names."""
        athletes: dict[str, dict[str, Any]] = {}
        for payload in pages:
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                athlete_id = str(item.get("id") or "").strip()
                name = str(
                    item.get("displayName")
                    or item.get("fullName")
                    or item.get("shortName")
                    or ""
                ).strip()
                if not athlete_id.isdigit() or not name:
                    continue
                birth_place = item.get("birthPlace") or {}
                athletes[athlete_id] = {
                    "id": athlete_id,
                    "kind": "athlete",
                    "displayName": name,
                    "location": str(
                        birth_place.get("summary")
                        if isinstance(birth_place, dict)
                        else ""
                    ).strip(),
                    "competitions": {},
                }
        return list(athletes.values())

    async def _search_individual_sport(
        self,
        term: str,
    ) -> list[dict[str, Any]]:
        """Search canonical athletes using ESPN's available capabilities."""
        # Fast path. ESPN's server-side sport filter is leaky, but
        # _search_individual_candidates validates every returned item's
        # own sport before accepting its canonical ID.
        candidates = await self._search_individual_candidates(
            term
        )

        if candidates:
            return candidates

        catalog = await self._league_catalog()
        semaphore = asyncio.Semaphore(3)

        async def search_collection(
            league_path: str,
        ) -> list[dict[str, Any]]:
            async with semaphore:
                pages = await self._athlete_collection_pages(
                    league_path
                )

            return [
                athlete
                for athlete in self._athletes_from_pages(pages)
                if (
                    self._matches_search(
                        term,
                        athlete["displayName"],
                    )
                    or term.strip() == athlete["id"]
                )
            ]

        collection_responses = await asyncio.gather(
            *(
                search_collection(league_path)
                for league_path in catalog
            )
        )

        found: dict[str, dict[str, Any]] = {}

        for athletes in collection_responses:
            for athlete in athletes:
                found.setdefault(
                    athlete["id"],
                    athlete,
                )

        if found:
            return sorted(
                found.values(),
                key=lambda item: self._match_rank(
                    term,
                    item["displayName"],
                ),
            )

        # Final capability fallback. Racing and some other ESPN feeds can
        # expose competitors in real events while providing no athlete
        # collection at all. Event participation gives us a canonical
        # competitor identity without assuming league membership.
        event_semaphore = asyncio.Semaphore(5)

        async def search_events(
            league_path: str,
            label: str,
        ) -> tuple[str, str, list[dict[str, Any]]]:
            async with event_semaphore:
                payloads = await self._event_discovery_payloads(
                    league_path
                )

            event_candidates: dict[str, dict[str, Any]] = {}
            resolved_label = label

            for payload in payloads:
                resolved_label = self._league_label(
                    payload,
                    resolved_label,
                )

                for athlete in self._event_candidates_from_payload(
                    payload,
                    "athlete",
                ):
                    if (
                        self._matches_search(
                            term,
                            athlete["displayName"],
                        )
                        or term.strip() == athlete["id"]
                    ):
                        event_candidates.setdefault(
                            athlete["id"],
                            athlete,
                        )

            return (
                league_path,
                resolved_label,
                list(event_candidates.values()),
            )

        event_responses = await asyncio.gather(
            *(
                search_events(
                    league_path,
                    label,
                )
                for league_path, label in catalog.items()
            )
        )

        found = {}

        for league_path, label, athletes in event_responses:
            for athlete in athletes:
                athlete_id = athlete["id"]

                existing = found.setdefault(
                    athlete_id,
                    dict(athlete),
                )

                existing.setdefault(
                    "competitions",
                    {},
                )[league_path] = label

        return sorted(
            found.values(),
            key=lambda item: self._match_rank(
                term,
                item["displayName"],
            ),
        )

    # ------------------------------------------------------------------
    # Athlete competition verification: actual matches are the truth source
    # ------------------------------------------------------------------

    @staticmethod
    def _competition_ids(events: list[dict]) -> set[str]:
        """Return actual match/competition IDs from filtered ESPN events."""
        ids: set[str] = set()
        for event in events:
            for _grouping, competition in iter_competitions(event):
                competition_id = str(competition.get("id") or "").strip()
                if competition_id:
                    ids.add(competition_id)
        return ids

    @staticmethod
    def _verification_dates() -> str:
        """Return a broad event window used only to verify specific options."""
        today = datetime.now(timezone.utc).date()
        return "{}-{}".format(
            (today - timedelta(days=120)).strftime("%Y%m%d"),
            (today + timedelta(days=365)).strftime("%Y%m%d"),
        )

    async def _verified_team_competitions(
        self, candidate: dict[str, Any]
    ) -> dict[str, str]:
        """Return team competitions backed by an actual ESPN event/schedule."""
        team_id = str(candidate.get("id") or "")
        candidates = dict(candidate.get("competitions") or {})
        if not team_id.isdigit() or not candidates:
            return {}

        semaphore = asyncio.Semaphore(8)

        async def verify(path: str, fallback_label: str):
            url = f"{SITE_BASE_URL}/{self._sport_path}/{path}/teams/{team_id}/schedule"
            async with semaphore:
                current, future = await asyncio.gather(
                    self._json(url),
                    self._json(url, {"fixture": "true"}),
                )

            payloads = [
                payload
                for payload in (current, future)
                if isinstance(payload, dict)
            ]
            events = merge_matching_events(payloads, team_id)
            if events:
                label = fallback_label
                for payload in payloads:
                    label = self._league_label(payload, label)
                return path, label, True

            # Some sport/league combinations do not expose a team schedule.
            # Verify against the real scoreboard before dropping the option.
            async with semaphore:
                scoreboard = await self._json(
                    f"{SITE_BASE_URL}/{self._sport_path}/{path}/scoreboard",
                    {"limit": "1000", "dates": self._verification_dates()},
                )
            if not scoreboard:
                return path, fallback_label, False
            events = merge_matching_events([scoreboard], team_id)
            return (
                path,
                self._league_label(scoreboard, fallback_label),
                bool(events),
            )

        responses = await asyncio.gather(
            *(verify(path, label) for path, label in candidates.items())
        )
        return {path: label for path, label, verified in responses if verified}

    async def _verified_athlete_competitions(self, athlete_id: str) -> dict[str, str]:
        """Return only league feeds with real events containing this athlete ID."""
        catalog = await self._league_catalog()
        semaphore = asyncio.Semaphore(8)
        dates = self._verification_dates()

        async def verify(path: str, fallback_label: str):
            url = f"{SITE_BASE_URL}/{self._sport_path}/{path}/scoreboard"
            async with semaphore:
                payload = await self._json(
                    url,
                    {"limit": "1000", "dates": dates},
                )
                if not payload:
                    # A few ESPN scoreboards reject broad date windows. A plain
                    # request is still useful evidence if it contains the athlete.
                    payload = await self._json(url, {"limit": "1000"})
            if not payload:
                return path, fallback_label, set()
            events = merge_matching_events([payload], athlete_id)
            return (
                path,
                self._league_label(payload, fallback_label),
                self._competition_ids(events),
            )

        responses = await asyncio.gather(
            *(verify(path, label) for path, label in catalog.items())
        )
        event_sets = {
            path: (label, event_ids)
            for path, label, event_ids in responses
            if event_ids
        }

        # Some ESPN tennis endpoints mirror another tour's matches. A feed is
        # not claimed as a verified competition if its entire match set is only
        # a strict subset of another feed. Equal duplicate feeds are ambiguous,
        # so neither label is presented; universal All still remains available.
        drop: set[str] = set()
        items = list(event_sets.items())
        for path, (_label, event_ids) in items:
            for other_path, (_other_label, other_ids) in items:
                if path == other_path:
                    continue
                if event_ids < other_ids:
                    drop.add(path)

        equal_groups: dict[frozenset[str], list[str]] = defaultdict(list)
        for path, (_label, event_ids) in items:
            equal_groups[frozenset(event_ids)].append(path)
        for paths in equal_groups.values():
            if len(paths) > 1:
                drop.update(paths)

        return {
            path: label
            for path, (label, _event_ids) in event_sets.items()
            if path not in drop
        }

    # ------------------------------------------------------------------
    # Result labels and entry creation
    # ------------------------------------------------------------------

    async def _search(self, term: str) -> list[dict[str, Any]]:
        """Dispatch to a team or athlete search inside the selected sport."""
        if self._sport_path in INDIVIDUAL_SPORTS:
            return await self._search_individual_sport(term)
        return await self._search_team_sport(term)

    @staticmethod
    def _result_labels(results: list[dict[str, Any]]) -> list[tuple[str, str]]:
        """Build readable labels while deduplicating only canonical ESPN IDs."""
        name_counts: dict[str, int] = defaultdict(int)
        for item in results:
            name_counts[str(item.get("displayName") or "").casefold()] += 1

        labels: list[tuple[str, str]] = []
        for item in results:
            item_id = str(item["id"])
            name = str(item["displayName"])
            details: list[str] = []

            competitions = sorted(
                {str(value) for value in (item.get("competitions") or {}).values()}
            )
            if competitions:
                details.extend(competitions[:3])

            location = str(item.get("location") or "").strip()
            abbreviation = str(item.get("abbreviation") or "").strip()
            if location and location.casefold() not in name.casefold():
                details.append(location)
            if abbreviation and abbreviation.casefold() not in name.casefold():
                details.append(abbreviation)

            label = name if not details else f"{name} ({' · '.join(details)})"
            labels.append((f"{item['kind']}:{item_id}", label))
        return labels

    def _native_league_id(self, league_path: str) -> str:
        """Return the existing Team Tracker league ID for a known native path."""
        for league_id, values in NATIVE_LEAGUES.items():
            if (
                values.get(CONF_SPORT_PATH) == self._sport_path
                and values.get(CONF_LEAGUE_PATH) == league_path
            ):
                return league_id
        return "XXX"

    async def _localized_all_competitions(self) -> str:
        """Return the translated All competitions label with English fallback."""
        try:
            translations = await async_get_translations(
                self.hass,
                self.hass.config.language,
                "selector",
                {DOMAIN},
            )
            return translations.get(
                f"component.{DOMAIN}.selector.competition.options.all_competitions",
                "All competitions",
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Could not load competition selector translation: %s", err)
            return "All competitions"

    async def _create_entry(self, league_path: str) -> config_entries.FlowResult:
        """Create a normal Team Tracker entry with canonical competitor ID."""
        league_id = (
            "XXX"
            if league_path == "all"
            else self._native_league_id(league_path)
        )
        runtime_competitor = (
            self._competitor_name
            if self._competitor_kind == "athlete"
            else self._competitor_id
        )
        data: dict[str, Any] = {
            CONF_NAME: self._competitor_name,
            CONF_LEAGUE_ID: league_id,
            CONF_TEAM_ID: runtime_competitor,
            CONF_SPORT_PATH: self._sport_path,
            CONF_LEAGUE_PATH: league_path,
        }

        if "college" in league_path and self._competitor_kind == "team":
            try:
                provider = get_provider(
                    self._sport_path, league_path, self._competitor_id
                )
                conference_id = await provider.async_get_team_conference_id(
                    self.hass,
                    self._sport_path,
                    league_path,
                    self._competitor_id,
                )
                if conference_id:
                    data[CONF_CONFERENCE_ID] = conference_id
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.debug("Conference detection failed: %s", err)

        return self.async_create_entry(title=self._competitor_name, data=data)

    # ------------------------------------------------------------------
    # Step 1: Sport
    # ------------------------------------------------------------------

    @staticmethod
    def _soccer_teams_from_payload(payload: dict) -> list[dict]:
        """Extract canonical teams from one ESPN soccer league response."""
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

    async def _async_soccer_all_league_paths(self) -> list[str]:
        """Discover real ESPN soccer leagues instead of using /soccer/all/teams."""
        paths: set[str] = set()

        # Keep Team Tracker's known soccer leagues as a fallback if the live
        # catalog is temporarily incomplete, but never treat "all" as a league.
        for values in NATIVE_LEAGUES.values():
            if values.get(CONF_SPORT_PATH) != "soccer":
                continue
            league_path = str(values.get(CONF_LEAGUE_PATH) or "").strip()
            if league_path and league_path != "all":
                paths.add(league_path)

        session = async_get_clientsession(self.hass)
        url = f"{CORE_BASE_URL}/v2/sports/soccer/leagues"
        try:
            async with session.get(url, params={"limit": "1000"}) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "ESPN soccer league catalog returned HTTP %s",
                        response.status,
                    )
                    return sorted(paths)
                payload = await response.json(content_type=None)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Could not discover ESPN soccer league catalog: %s", err)
            return sorted(paths)

        if isinstance(payload, dict):
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                league_path = str(item.get("slug") or "").strip()
                ref = str(item.get("$ref") or "")
                if not league_path and ref:
                    match = re.search(r"/leagues/([^/?#]+)", ref)
                    if match:
                        league_path = unquote(match.group(1))
                if league_path and league_path != "all":
                    paths.add(league_path)

        return sorted(paths)

    async def _async_get_soccer_all_teams(self) -> list[dict]:
        """Merge real soccer league collections by canonical ESPN team ID."""
        if getattr(self, "_soccer_all_team_cache", None) is not None:
            return self._soccer_all_team_cache

        league_paths = await self._async_soccer_all_league_paths()
        semaphore = asyncio.Semaphore(12)

        async def fetch(league_path: str) -> list[dict]:
            async with semaphore:
                return await self._async_fetch_soccer_league_teams(league_path)

        responses = await asyncio.gather(
            *(fetch(league_path) for league_path in league_paths)
        )

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
        if result:
            self._soccer_all_team_cache = result
        return result

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Choose the sport before searching a competitor."""
        self._errors = {}
        if user_input is not None:
            sport = str(user_input["sport"])
            if sport == CUSTOM_SPORT:
                return await self.async_step_custom_api()
            self._sport_path = sport
            return await self.async_step_search()

        sport_selector = SelectSelector(
            SelectSelectorConfig(
                options=list(SPORTS),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="sport",
            )
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("sport"): sport_selector}),
            errors=self._errors,
            last_step=False,
        )

    # ------------------------------------------------------------------
    # Step 2: Search team/athlete in selected sport
    # ------------------------------------------------------------------

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Search canonical competitors within only the selected sport."""
        self._errors = {}
        if user_input is not None:
            term = str(user_input.get("search_competitor") or "").strip()
            if not term:
                self._errors["search_competitor"] = "search_required"
            else:
                results = await self._search(term)
                if not results:
                    self._errors["search_competitor"] = "no_competitors_found"
                else:
                    self._results = {
                        f"{item['kind']}:{item['id']}": item for item in results
                    }
                    return await self.async_step_select_competitor()

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema(
                {vol.Required("search_competitor"): cv.string}
            ),
            errors=self._errors,
            last_step=False,
        )

    # ------------------------------------------------------------------
    # Step 3: Select canonical result
    # ------------------------------------------------------------------

    async def async_step_select_competitor(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Choose one canonical team/athlete from the search results."""
        if user_input is not None:
            selected = self._results[str(user_input["competitor"])]
            self._competitor_id = str(selected["id"])
            self._competitor_name = str(selected["displayName"])
            self._competitor_kind = str(selected["kind"])

            if self._competitor_kind == "athlete":
                competitions = await self._verified_athlete_competitions(
                    self._competitor_id
                )
            else:
                competitions = await self._verified_team_competitions(selected)

            all_label = await self._localized_all_competitions()
            options = [(ALL_COMPETITIONS, all_label)]
            options.extend(
                sorted(competitions.items(), key=lambda item: item[1].casefold())
            )
            self._competition_options = dict(options)
            return await self.async_step_competition()

        return self.async_show_form(
            step_id="select_competitor",
            data_schema=vol.Schema(
                {
                    vol.Required("competitor"): _dropdown(
                        self._result_labels(list(self._results.values()))
                    )
                }
            ),
            errors={},
            last_step=False,
        )

    # ------------------------------------------------------------------
    # Step 4: All competitions or one verified competition
    # ------------------------------------------------------------------

    async def async_step_competition(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Choose universal tracking or one verified competition."""
        if user_input is not None:
            selected = str(user_input["competition"])
            league_path = "all" if selected == ALL_COMPETITIONS else selected
            return await self._create_entry(league_path)

        return self.async_show_form(
            step_id="competition",
            data_schema=vol.Schema(
                {
                    vol.Required("competition"): _dropdown(
                        list(self._competition_options.items())
                    )
                }
            ),
            errors={},
            description_placeholders={"competitor_name": self._competitor_name},
            last_step=True,
        )

    # ------------------------------------------------------------------
    # Advanced / Custom API escape hatch
    # ------------------------------------------------------------------

    async def async_step_custom_api(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Keep the technical manual API setup for unsupported/advanced use."""
        if user_input is not None:
            sport_path = str(user_input[CONF_SPORT_PATH]).strip()
            league_path = str(user_input[CONF_LEAGUE_PATH]).strip()
            competitor_id = str(user_input[CONF_TEAM_ID]).strip()
            name = str(user_input.get(CONF_NAME) or competitor_id).strip()
            data: dict[str, Any] = {
                CONF_NAME: name,
                CONF_LEAGUE_ID: "XXX",
                CONF_TEAM_ID: competitor_id,
                CONF_SPORT_PATH: sport_path,
                CONF_LEAGUE_PATH: league_path,
            }
            conference_id = str(user_input.get(CONF_CONFERENCE_ID) or "").strip()
            if conference_id:
                data[CONF_CONFERENCE_ID] = conference_id
            return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="custom_api",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SPORT_PATH): cv.string,
                    vol.Required(CONF_LEAGUE_PATH): cv.string,
                    vol.Required(CONF_TEAM_ID): cv.string,
                    vol.Optional(CONF_CONFERENCE_ID, default=""): cv.string,
                    vol.Optional(CONF_NAME, default=""): cv.string,
                }
            ),
            errors={},
            last_step=True,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return Team Tracker's existing options flow."""
        return TeamTrackerScoresOptionsFlow(config_entry)


class TeamTrackerScoresOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Team Tracker."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.entry = config_entry
        self._options: dict[str, Any] = dict(config_entry.options)
        self._errors: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage API language options."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        lang = None
        if self.entry.options and CONF_API_LANGUAGE in self.entry.options:
            lang = self.entry.options[CONF_API_LANGUAGE]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_API_LANGUAGE,
                        description={"suggested_value": lang},
                        default="",
                    ): cv.string
                }
            ),
            errors=self._errors,
        )
