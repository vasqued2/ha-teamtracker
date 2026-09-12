""" Provide response from the Live Tennis API """
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
from typing import TYPE_CHECKING, Any

import aiohttp
import arrow
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, OVERRIDE_DICT
from .provider_base import BaseSportProvider

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

#
# Live Tennis API Definitions
#
# API documentation:
#    https://docs.livetennisapi.com/llms.txt
#    https://docs.livetennisapi.com/openapi.yaml
#
# The API key is sent as an X-API-Key header.  It never appears in a URL, a log
# line, a snapshot or a config entry.  Without a key this provider is never
# selected and the Live Tennis leagues are not offered in the config flow, so
# the integration behaves exactly as it did before (see resolve_api_key).
#
DATA_PROVIDER_LIVETENNIS = "livetennis"
LT_DATA_FORMAT = "lt-json"
LIVETENNIS_BASE_URL = "https://api.livetennisapi.com/api/public/v1/matches"
LIVETENNIS_API_KEY_ENV = "LIVETENNIS_API_KEY"

# limit: default 50, maximum 200 (openapi.yaml #/components/parameters/limit)
LT_LIMIT = 200

#
# Tours offered by the API.  league_path is the `tour` query value verbatim
# (openapi.yaml #/components/parameters/tour: atp|wta|challenger|itf|juniors).
#
LT_TOURS = {
    "atp": "ATP Tour",
    "wta": "WTA Tour",
    "challenger": "ATP Challenger Tour",
    "itf": "ITF World Tennis Tour",
    "juniors": "Junior Grand Slam",
}

#
# Match.status -> ESPN competition state.  A cancelled match is terminal, so it
# reads as "post" and says why in the status detail.  An unknown status is
# skipped rather than guessed: the API may add values within v1.
#
LT_STATE_MAP = {
    "upcoming": "pre",
    "live": "in",
    "completed": "post",
    "cancelled": "post",
}

#
# Match.outcome -> the POST status detail shown in the `clock` attribute.
#
LT_OUTCOME_DETAIL = {
    "completed": "Final",
    "retired": "Final - Retired",
    "walkover": "Walkover",
    "default": "Final - Default",
    "abandoned": "Abandoned",
    "unresolved": "Unresolved",
}

#
#  Per-status polling cost, against the FREE tier's 100 requests/day
#  (30/min, 100/day - https://docs.livetennisapi.com/llms.txt "Plans").
#
#    status=live       one call per coordinator refresh.  At the 15 minute
#                      DEFAULT_REFRESH_RATE below that is 1440/15 = 96 calls/day.
#    status=upcoming   FREE, but a start list does not move minute to minute, so
#                      it is polled off its own 8 hour cache = 3 calls/day.
#    status=completed  BASIC and above (`403 upgrade_required` on a FREE key).
#                      Also on the 8 hour cache = 3 calls/day where it is
#                      allowed; a FREE key spends exactly one call discovering
#                      the 403 and is never asked again this session.
#
#  FREE total, steady state: 96 + 3 = 99 calls/day, inside 100.
#  BASIC and above:          96 + 3 + 3 = 102 calls/day, against 1,000/day.
#
LT_CACHE_UPCOMING = "livetennis_upcoming"
LT_CACHE_COMPLETED = "livetennis_completed"
LT_SLOW_CACHE_DURATION = timedelta(hours=8)

# Status listings reachable on a FREE key
LT_STATUS_LIVE = "live"
LT_STATUS_UPCOMING = "upcoming"
LT_STATUS_COMPLETED = "completed"


#
#  resolve_api_key()
#
def resolve_api_key(hass: HomeAssistant | None, league_path: str = "") -> str:
    """Return the configured Live Tennis API key, or "" when there is none.

    Checked in order:

      1. the override file, per league:  livetennis -> <league_path> -> api_key
      2. the override file, shared by every league:  livetennis -> api_key
      3. the LIVETENNIS_API_KEY environment variable

    The override file is the house pattern for provider credentials and is the
    only one reachable on a Home Assistant OS install, where the core process
    environment is not the user's to set.  Both setup paths load the override
    dict before building a coordinator (__init__.py and sensor.py), so this is
    safe to read synchronously from the provider factory.

    Callers treat the result as a secret: it is only ever put in a request
    header, never logged or returned in an attribute.
    """

    if hass is not None:
        sport_config = (
            hass.data.get(DOMAIN, {}).get(OVERRIDE_DICT, {}) or {}
        ).get(DATA_PROVIDER_LIVETENNIS, {})

        if isinstance(sport_config, dict):
            league_config = sport_config.get(league_path.lower(), {})
            if isinstance(league_config, dict):
                key = str(league_config.get("api_key", "") or "").strip()
                if key:
                    return key

            key = str(sport_config.get("api_key", "") or "").strip()
            if key:
                return key

    return os.environ.get(LIVETENNIS_API_KEY_ENV, "").strip()


class LiveTennisProvider(BaseSportProvider):
    """Provider for Live Tennis API data.

    Converts the API payload into the ESPN JSON format so that the existing
    ESPN parser and set_tennis logic are reused (the second of the two provider
    patterns described in CONTRIBUTING.md).
    """

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        super().__init__(coordinator)
        self.DATA_PROVIDER: str = DATA_PROVIDER_LIVETENNIS
        self.data_format = LT_DATA_FORMAT
        self.ATTRIBUTION: str = "Powered by livetennisapi.com"

        #
        #  Cadence.  The FREE tier allows 100 requests/day, so the refresh rate
        #  is the binding constraint rather than a latency preference:
        #
        #    15 min  1440/15 = 96 calls/day          <- DEFAULT, and the whole budget
        #     5 sec  720 calls/hour                  the free day is gone in ~8 minutes
        #    60 sec  60 calls/hour                   the free day is gone in ~100 minutes
        #
        #  RAPID_REFRESH_RATE is therefore deliberately EQUAL to the default:
        #  the coordinator switches to it while a tracked match is in play, and
        #  on 100 calls/day there is no headroom to accelerate into.  Even a
        #  10 minute in-play rate costs an extra ~10 calls over a five set
        #  match, which 96 + 10 does not fit.  A paid key (BASIC 1,000/day,
        #  PRO 10,000/day) would comfortably carry a much faster in-play rate.
        #
        self.DEFAULT_REFRESH_RATE: timedelta = timedelta(minutes=15)
        self.RAPID_REFRESH_RATE: timedelta = timedelta(minutes=15)

        # Status listings this key is not entitled to; probed once, then skipped
        self._upgrade_required: set[str] = set()

    #
    #  _get_cache_key()
    #    Return unique key for Live Tennis calls
    #
    def _get_cache_key(self) -> str:
        """Return cache key"""

        if not self._coordinator:
            return ""

        return (
            self.DATA_PROVIDER
            + ":"
            + self._coordinator.sport_path
            + ":"
            + self._coordinator.league_path
        )

    #
    #  _async_fetch_scoreboard_data()
    #
    async def _async_fetch_scoreboard_data(
        self,
        hass,
        lang: str,
    ) -> dict:
        """Fetch the slate from the Live Tennis API and return an ESPN-compatible dict."""

        if not self._coordinator:
            return {"data": None, "url": None, "timestamp": None}

        await self._async_load_override_dict(hass)

        sensor_name = self._coordinator.name
        league_path = self._coordinator.league_path
        league_id = league_path.upper()
        tour = league_path.lower()

        timestamp = arrow.now().format(arrow.FORMAT_W3C)

        if tour not in LT_TOURS:
            _LOGGER.warning(
                "%s: '%s' is not a Live Tennis API tour, expected one of %s",
                sensor_name,
                league_path,
                ", ".join(sorted(LT_TOURS)),
            )
            return {"data": None, "url": None, "timestamp": timestamp}

        #
        #  status=live is the time critical listing and is fetched every
        #  refresh.  upcoming and completed sit behind their own slow cache so
        #  a refresh costs one request.  See the budget note above.
        #
        live = await self._async_get_status_matches(
            hass, tour, LT_STATUS_LIVE, sensor_name
        )
        upcoming = await self._async_get_status_matches(
            hass, tour, LT_STATUS_UPCOMING, sensor_name, LT_CACHE_UPCOMING
        )
        completed = await self._async_get_status_matches(
            hass, tour, LT_STATUS_COMPLETED, sensor_name, LT_CACHE_COMPLETED
        )

        url = live["url"] or upcoming["url"] or completed["url"]

        #
        #  Only report an API error when nothing at all could be read.  A
        #  cached start list is still worth parsing if the live call failed.
        #
        if (
            live["data"] is None
            and upcoming["data"] is None
            and completed["data"] is None
        ):
            return {"data": None, "url": url, "timestamp": timestamp}

        #
        #  Deduplicate by match id.  A match can sit in a freshly read live
        #  listing and in a cached upcoming listing at the same time; the
        #  fresher lifecycle wins so the parser never sees the same match twice.
        #
        matches: dict[str, dict] = {}
        for response in (live, completed, upcoming):
            for match in response["data"] or []:
                if not isinstance(match, dict):
                    continue
                match_id = str(match.get("id", ""))
                if match_id and match_id not in matches:
                    matches[match_id] = match

        espn_data = self._transform_livetennis_to_espn(
            list(matches.values()), tour, league_id
        )

        return {"data": espn_data, "url": url, "timestamp": timestamp}

    #
    #  _async_get_status_matches()
    #    One lifecycle listing, from the slow cache when cache_name is given
    #
    async def _async_get_status_matches(
        self,
        hass,
        tour: str,
        status: str,
        sensor_name: str,
        cache_name: str | None = None,
    ) -> dict:
        """Return {"data": list|None, "url": str|None} for one lifecycle status."""

        #  This key is not entitled to the listing; do not spend the call again
        if status in self._upgrade_required:
            return {"data": None, "url": None, "timestamp": None}

        key = self._get_cache_key() + ":" + status

        if cache_name:
            cached = self._get_from_cache(cache_name, key, LT_SLOW_CACHE_DURATION)
            if cached:
                return cached

        params: dict[str, Any] = {
            "status": status,
            "tour": tour,
            "limit": LT_LIMIT,
        }

        lt_response = await self.async_call_livetennis_api(
            hass, LIVETENNIS_BASE_URL, params, sensor_name, tour
        )

        lt_data = lt_response["lt_data"]
        url = lt_response["url"]
        timestamp = lt_response["timestamp"]

        if lt_response.get("status") == 403:
            self._upgrade_required.add(status)
            _LOGGER.info(
                "%s: Live Tennis API plan does not include the '%s' listing; "
                "skipping it. Scores for matches already played need BASIC or above.",
                sensor_name,
                status,
            )
            return {"data": None, "url": url, "timestamp": timestamp}

        #  List endpoints return {data, meta}
        data = None
        if isinstance(lt_data, dict):
            raw = lt_data.get("data")
            if isinstance(raw, list):
                data = raw

        response = {"data": data, "url": url, "timestamp": timestamp}

        if cache_name and data is not None:
            self._save_to_cache(cache_name, key, response)

        return response

    #
    #  _transform_livetennis_to_espn()
    #
    def _transform_livetennis_to_espn(
        self, matches: list[dict], tour: str, league_id: str
    ) -> dict:
        """Transform Live Tennis matches into ESPN-compatible format."""

        league_config: dict[str, Any] = {}
        if self._coordinator:
            league_config = (
                self._coordinator.hass.data.get(DOMAIN, {})
                .get(OVERRIDE_DICT, {})
                .get(DATA_PROVIDER_LIVETENNIS, {})
                .get(tour, {})
            ) or {}

        league: dict[str, Any] = {
            "id": tour,
            "abbreviation": league_id,
            "name": league_config.get("league_name", LT_TOURS.get(tour, "")),
        }

        #
        #  This feed carries no league artwork.  Only publish a logo when the
        #  user has configured one, so that league_logo falls back to the same
        #  placeholder every other unconfigured logo in the integration uses.
        #
        league_logo = league_config.get("league_logo", "")
        if league_logo:
            league["logos"] = [{"href": league_logo}]

        espn_data: dict[str, Any] = {
            "leagues": [league],
            "events": [],
        }

        events = []
        for match in matches:
            event = self._build_espn_event(match)
            if event is not None:
                events.append(event)

        #  Chronological, as an ESPN scoreboard is
        events.sort(key=lambda e: str(e.get("date", "")))
        espn_data["events"] = events

        return espn_data

    #
    #  _build_espn_event()
    #
    def _build_espn_event(self, match: dict) -> dict | None:
        """Build a single ESPN-format event from one Live Tennis match."""

        state = LT_STATE_MAP.get(str(match.get("status", "")).lower())
        if state is None:
            return None

        #
        #  A suspended match is paused, not over (Match.event_status
        #  "Interrupted"), so it stays in play.
        #
        event_status = match.get("event_status")
        if event_status == "Interrupted":
            state = "in"

        #
        #  The parser needs a usable date for every event it looks at, so a
        #  match with no instant at all is skipped rather than defaulted.
        #
        espn_date = self._convert_to_espn_date(
            match.get("scheduled_time") or match.get("live_at")
        )
        if not espn_date:
            return None

        players = match.get("players")
        if not isinstance(players, dict):
            return None

        score = match.get("score")
        if not isinstance(score, dict):
            score = {}

        p1_linescores, p2_linescores = self._build_linescores(score)

        competitor = self._build_competitor(
            players.get("p1"), match, score, p1_linescores, 0
        )
        opponent = self._build_competitor(
            players.get("p2"), match, score, p2_linescores, 1
        )
        if competitor is None or opponent is None:
            return None

        if state == "post":
            winner = match.get("winner")
            if winner in (1, 2):
                competitor["winner"] = winner == 1
                opponent["winner"] = winner == 2

        match_id = str(match.get("id", ""))
        detail = self._build_status_detail(match, score, state, espn_date)

        competition: dict[str, Any] = {
            "id": match_id,
            "date": espn_date,
            "venue": {"fullName": match.get("tournament") or ""},
            "competitors": [competitor, opponent],
            "status": {
                #  The set in progress, reported as the period
                "period": len(p1_linescores),
                "type": {
                    "state": state,
                    "detail": detail,
                    "shortDetail": detail,
                },
            },
            "odds": [],
        }

        #  Free text round label, e.g. "Quarterfinal"
        if match.get("round"):
            competition["round"] = {"displayName": match["round"]}

        #  Match.draw is honestly three valued: null is not singles
        if match.get("draw"):
            competition["type"] = {"text": str(match["draw"]).title()}

        event: dict[str, Any] = {
            "id": match_id,
            "date": espn_date,
            "name": self._build_event_name(players, " v "),
            "shortName": self._build_event_name(players, " v "),
            "season": {"slug": espn_date[:4]},
            "status": {
                "type": {
                    "state": state,
                    "shortDetail": detail,
                },
            },
            "competitions": [competition],
        }

        return event

    #
    #  _build_competitor()
    #
    def _build_competitor(
        self,
        player: Any,
        match: dict,
        score: dict,
        linescores: list[dict],
        index: int,
    ) -> dict | None:
        """Build an ESPN-format athlete competitor from one Live Tennis player."""

        if not isinstance(player, dict):
            return None

        name = str(player.get("name") or "").strip()
        if not name:
            return None

        sets = score.get("sets")
        set_score = None
        if isinstance(sets, list) and len(sets) > index:
            set_score = self._as_int(sets[index])

        competitor: dict[str, Any] = {
            "id": str(player.get("id", "")),
            "type": "athlete",
            "order": index,
            "winner": None,
            "score": None if set_score is None else str(set_score),
            "athlete": {
                "id": str(player.get("id", "")),
                "displayName": name,
                "shortName": name.split()[-1],
            },
            "linescores": linescores,
        }

        #
        #  set_tennis reads team_rank from tournamentSeed.  Our feed carries no
        #  seed, so this is Player.ranking, the official singles ranking
        #  position (null for doubles teams and most ITF/junior players).
        #
        ranking = self._as_int(player.get("ranking"))
        if ranking is not None:
            competitor["tournamentSeed"] = ranking

        return competitor

    #
    #  _build_linescores()
    #
    def _build_linescores(self, score: dict) -> tuple[list[dict], list[dict]]:
        """Build both players' per-set linescores from a player-major games array.

        Score.games is [[games_p1...], [games_p2...]], so [[6,3,2],[4,6,1]]
        reads 6-4, 3-6, 2-1.  Completed matches are observed carrying an EMPTY
        games array and NULL points, so nothing here may assume a value is
        present: set_tennis calls int() on every linescore value, and an empty
        list is the only safe answer when the games cannot be read.
        """

        games = score.get("games")
        if not isinstance(games, list) or len(games) < 2:
            return [], []

        p1_games, p2_games = games[0], games[1]
        if not isinstance(p1_games, list) or not isinstance(p2_games, list):
            return [], []

        #  Only sets both players have a game count for can be compared
        sets_count = min(len(p1_games), len(p2_games))
        if sets_count == 0:
            return [], []

        p1_values = [self._as_int(g) for g in p1_games[:sets_count]]
        p2_values = [self._as_int(g) for g in p2_games[:sets_count]]
        if None in p1_values or None in p2_values:
            return [], []

        p1_linescores: list[dict[str, Any]] = [{"value": v} for v in p1_values]
        p2_linescores: list[dict[str, Any]] = [{"value": v} for v in p2_values]

        #
        #  In a tiebreak, Score.points holds the running tiebreak count as
        #  plain integer strings, and it belongs to the set in progress only.
        #
        if score.get("is_tiebreak"):
            points = score.get("points")
            if isinstance(points, list) and len(points) >= 2:
                if points[0] is not None:
                    p1_linescores[-1]["tiebreak"] = str(points[0])
                if points[1] is not None:
                    p2_linescores[-1]["tiebreak"] = str(points[1])

        return p1_linescores, p2_linescores

    #
    #  _build_status_detail()
    #
    def _build_status_detail(
        self, match: dict, score: dict, state: str, espn_date: str
    ) -> str:
        """Build the status detail string shown in the `clock` attribute."""

        if state == "pre":
            return espn_date[-6:]

        if state == "in":
            if match.get("event_status") == "Interrupted":
                return "Suspended"
            return self._build_in_play_detail(match, score)

        #  POST
        outcome = str(match.get("outcome") or "")
        detail = LT_OUTCOME_DETAIL.get(outcome, "")
        if not detail:
            if str(match.get("status", "")).lower() == "cancelled":
                detail = str(match.get("event_status") or "Cancelled")
            else:
                detail = "Final"

        #
        #  A completed match can carry an empty games array, in which case
        #  there are no linescores for set_tennis to count sets from.  Say the
        #  sets score here rather than let the match read as if it were 0-0.
        #
        if not self._build_linescores(score)[0]:
            sets = score.get("sets")
            if isinstance(sets, list) and len(sets) >= 2:
                s1 = self._as_int(sets[0])
                s2 = self._as_int(sets[1])
                if s1 is not None and s2 is not None:
                    detail = f"{detail} ({s1}-{s2} sets)"

        return detail

    #
    #  _build_in_play_detail()
    #
    def _build_in_play_detail(self, match: dict, score: dict) -> str:
        """Describe the state of a match in play."""

        parts = []

        games = score.get("games")
        if isinstance(games, list) and games and isinstance(games[0], list):
            parts.append(f"Set {len(games[0])}")

        #
        #  In-game points are tennis strings ("0", "15", "30", "40", "AD")
        #  except in a tiebreak, where they are the running integer count.
        #  Either can be null, so both are formatted defensively.
        #
        points = score.get("points")
        if isinstance(points, list) and len(points) >= 2:
            p1, p2 = points[0], points[1]
            if p1 is not None and p2 is not None:
                label = "Tiebreak " if score.get("is_tiebreak") else ""
                parts.append(f"{label}{p1}-{p2}")

        server = score.get("server")
        if server in (1, 2):
            players = match.get("players")
            if isinstance(players, dict):
                player = players.get("p1" if server == 1 else "p2")
                if isinstance(player, dict) and player.get("name"):
                    parts.append(f"{str(player['name']).split()[-1]} serving")

        return " - ".join(parts) if parts else "In Progress"

    #
    #  _build_event_name()
    #
    def _build_event_name(self, players: dict, separator: str) -> str:
        """Build the event name from both player names."""

        names = []
        for side in ("p1", "p2"):
            player = players.get(side)
            if isinstance(player, dict) and player.get("name"):
                names.append(str(player["name"]))
        return separator.join(names)

    #
    #  _convert_to_espn_date()
    #
    def _convert_to_espn_date(self, iso_str: Any) -> str:
        """Convert an API UTC timestamp to the ESPN date format (2026-03-19T23:00Z)."""

        if not iso_str or not isinstance(iso_str, str):
            return ""
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        except (ValueError, TypeError):
            return ""

    #
    #  _as_int()
    #
    def _as_int(self, value: Any) -> int | None:
        """Return value as an int, or None when it cannot be read as one."""

        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    #
    #  async_call_livetennis_api()
    #
    async def async_call_livetennis_api(
        self, hass, base_url, params, sensor_name, league_id
    ) -> dict:
        """Call the Live Tennis API.
            Response:
            {
                "lt_data":   JSON response from API or None
                "url":       URL for the call (never carries the API key)
                "timestamp": when the call was made
                "status":    HTTP status, or None if the call did not complete
            }
        """
        headers = {
            "User-Agent": self._USER_AGENT,
            "Accept": "application/json",
            "X-API-Key": resolve_api_key(hass, league_id),
        }
        session = async_get_clientsession(hass)

        url = str(URL(base_url).with_query(params))

        _LOGGER.debug(
            "%s: Calling Live Tennis API: %s",
            sensor_name,
            url,
        )
        timestamp = arrow.now().format(arrow.FORMAT_W3C)

        try:
            async with session.get(url, headers=headers) as r:
                status = r.status
                if status == 200:
                    lt_data = await r.json(content_type=None)
                else:
                    _LOGGER.debug(
                        "%s: Live Tennis API returned status %s for league '%s'",
                        sensor_name,
                        status,
                        league_id,
                    )
                    return {
                        "lt_data": None,
                        "url": url,
                        "timestamp": timestamp,
                        "status": status,
                    }
        except (aiohttp.ClientError, TimeoutError, ValueError) as e:
            _LOGGER.debug("%s: Live Tennis API call failed: %s", sensor_name, e)
            return {
                "lt_data": None,
                "url": url,
                "timestamp": timestamp,
                "status": None,
            }

        return {
            "lt_data": lt_data,
            "url": url,
            "timestamp": timestamp,
            "status": status,
        }
