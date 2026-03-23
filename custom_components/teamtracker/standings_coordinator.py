"""Standings coordinator for TeamTracker."""
from datetime import datetime, timezone
import logging

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import STANDINGS_REFRESH_RATE, STANDINGS_URL_BASE, USER_AGENT

_LOGGER = logging.getLogger(__name__)

# Stat abbreviations → standard field names (first match wins)
_STAT_MAP = [
    ("rank",            ["RK"]),
    ("points",          ["PTS"]),
    ("wins",            ["W"]),
    ("losses",          ["L"]),
    ("draws",           ["T", "D"]),
    ("games_played",    ["GP"]),
    ("goal_difference", ["DIFF"]),
    ("points_for",      ["PF", "GF"]),
    ("points_against",  ["PA", "GA"]),
    ("win_percent",     ["PCT", "WPCT"]),
    ("streak",          ["STRK"]),
]


def _parse_entry(entry: dict, group_name: str) -> dict:
    """Convert a raw standings entry into a clean dict."""
    team = entry.get("team", {})
    logos = team.get("logos") or team.get("logo") or []
    logo_href = logos[0].get("href", "") if isinstance(logos, list) and logos else ""

    stats_raw = entry.get("stats", [])
    raw_by_abbr = {}
    for s in stats_raw:
        abbr = (s.get("abbreviation") or s.get("name") or "").upper()
        val = s.get("value")
        if abbr and val is not None:
            raw_by_abbr[abbr] = val

    result = {
        "team_name": team.get("displayName", ""),
        "team_abbr": team.get("abbreviation", ""),
        "team_logo": logo_href,
        "group":     group_name,
    }
    for field, keys in _STAT_MAP:
        for k in keys:
            if k in raw_by_abbr:
                v = raw_by_abbr[k]
                result[field] = int(v) if isinstance(v, float) and v == int(v) else v
                break

    return result


class TeamTrackerStandingsCoordinator(DataUpdateCoordinator):
    """Fetches and caches a full league standings table."""

    def __init__(self, hass, sport_path: str, league_path: str, league_id: str, name: str) -> None:
        """Initialize."""
        self.sport_path = sport_path
        self.league_path = league_path
        self.league_id = league_id
        super().__init__(hass, _LOGGER, name=name, update_interval=STANDINGS_REFRESH_RATE)

    async def _async_update_data(self) -> dict:
        """Fetch standings from ESPN API."""
        url = f"{STANDINGS_URL_BASE}/{self.sport_path}/{self.league_path}/standings"
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, headers={"User-Agent": USER_AGENT}) as resp:
                if resp.status != 200:
                    if self.data:
                        return self.data
                    raise UpdateFailed(f"ESPN standings API returned HTTP {resp.status}")
                raw = await resp.json()
        except Exception as err:  # pylint: disable=broad-exception-caught
            if self.data:
                return self.data
            raise UpdateFailed(str(err)) from err

        entries_list = []
        children = raw.get("children") or [raw]
        for child in children:
            group_name = child.get("name", "")
            for entry in child.get("standings", {}).get("entries", []):
                entries_list.append(_parse_entry(entry, group_name))

        return {
            "standings":   entries_list,
            "league":      self.league_id,
            "sport":       self.sport_path,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
