"""Supplement ESPN soccer/all with missing upcoming fixtures."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .fixture_resolver import async_get_fixture_resolver, name_score, parse_datetime
from .provide_espn_all_resilient import ResilientEspnAllLeaguesProvider

_LOGGER = logging.getLogger(__name__)


class SupplementalEspnAllLeaguesProvider(ResilientEspnAllLeaguesProvider):
    """Keep ESPN authoritative while adding fixtures ESPN does not expose."""

    async def _async_fetch_scoreboard_data(
        self,
        hass: HomeAssistant,
        lang: str,
    ) -> dict:
        """Fetch ESPN data, then add only genuinely missing soccer fixtures."""
        response = await super()._async_fetch_scoreboard_data(hass, lang)

        if not self._coordinator or self._coordinator.sport_path.lower() != "soccer":
            return response

        team_id = str(self._coordinator.team_id)
        team_name, team_logo = self._tracked_team_meta(response, team_id)
        if not team_name:
            return response

        try:
            resolver = await async_get_fixture_resolver(hass)
            supplemental_events = await resolver.async_resolve_events(
                coordinator=self._coordinator,
                espn_team_id=team_id,
                team_name=team_name,
                team_logo=team_logo,
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            # Supplemental sources must never make a working ESPN sensor fail.
            _LOGGER.debug(
                "%s: supplemental fixture resolver failed: %s",
                self._coordinator.name,
                err,
            )
            return response

        if not supplemental_events:
            return response

        merged, added = self._merge_supplemental_events(
            response,
            supplemental_events,
            team_id,
        )
        for event in added:
            _LOGGER.debug(
                "%s: supplemental fixture source=%s id=%s date=%s",
                self._coordinator.name,
                event.get("_teamtracker_fixture_source"),
                event.get("id"),
                event.get("date"),
            )
        return merged

    @staticmethod
    def _team_id(competitor: dict[str, Any]) -> str:
        """Return a competitor's canonical team ID."""
        return str(
            competitor.get("id")
            or (competitor.get("team") or {}).get("id")
            or ""
        )

    @classmethod
    def _tracked_team_meta(cls, response: dict, team_id: str) -> tuple[str, str]:
        """Get the tracked team's ESPN name/logo without trusting sensor name."""
        for team in (response.get("lookups") or {}).get("team_list") or []:
            if not isinstance(team, dict) or str(team.get("id") or "") != team_id:
                continue
            name = str(team.get("displayName") or team.get("name") or "").strip()
            logo = str(team.get("logo") or "").strip()
            if name:
                return name, logo

        for event in (response.get("data") or {}).get("events") or []:
            if not isinstance(event, dict):
                continue
            for competition in event.get("competitions") or []:
                if not isinstance(competition, dict):
                    continue
                for competitor in competition.get("competitors") or []:
                    if not isinstance(competitor, dict) or cls._team_id(competitor) != team_id:
                        continue
                    team = competitor.get("team") or {}
                    name = str(team.get("displayName") or team.get("name") or "").strip()
                    logo = str(team.get("logo") or "").strip()
                    if name:
                        return name, logo
        return "", ""

    @classmethod
    def _fixture_identity(
        cls,
        event: dict[str, Any],
        team_id: str,
    ) -> tuple[datetime | None, str, bool | None]:
        """Return kickoff, opponent name and tracked home/away orientation."""
        kickoff = parse_datetime(event.get("date"))
        for competition in event.get("competitions") or []:
            if not isinstance(competition, dict):
                continue
            competitors = [
                competitor
                for competitor in competition.get("competitors") or []
                if isinstance(competitor, dict)
            ]
            tracked = next(
                (competitor for competitor in competitors if cls._team_id(competitor) == team_id),
                None,
            )
            if tracked is None:
                continue
            opponent = next((competitor for competitor in competitors if competitor is not tracked), None)
            opponent_team = (opponent or {}).get("team") or {}
            opponent_name = str(
                opponent_team.get("displayName")
                or opponent_team.get("name")
                or ""
            )
            home_away = str(tracked.get("homeAway") or "").lower()
            tracked_home: bool | None
            if home_away == "home":
                tracked_home = True
            elif home_away == "away":
                tracked_home = False
            else:
                tracked_home = None
            return kickoff, opponent_name, tracked_home
        return kickoff, "", None

    @classmethod
    def _events_equivalent(
        cls,
        left: dict[str, Any],
        right: dict[str, Any],
        team_id: str,
    ) -> bool:
        """Match one fixture across providers by kickoff, opponent and orientation."""
        left_time, left_opponent, left_home = cls._fixture_identity(left, team_id)
        right_time, right_opponent, right_home = cls._fixture_identity(right, team_id)
        if left_time is None or right_time is None:
            return False
        if abs((left_time - right_time).total_seconds()) > 15 * 60:
            return False
        if left_home is not None and right_home is not None and left_home != right_home:
            return False
        if left_opponent and right_opponent:
            return name_score(left_opponent, right_opponent) >= 0.78
        return False

    @classmethod
    def _merge_supplemental_events(
        cls,
        response: dict,
        supplemental_events: list[dict[str, Any]],
        team_id: str,
    ) -> tuple[dict, list[dict[str, Any]]]:
        """Merge missing fixtures, preserving ESPN when both sources know a match."""
        result = dict(response)
        data = dict(response.get("data") or {})
        events = [
            event
            for event in data.get("events") or []
            if isinstance(event, dict)
        ]
        added: list[dict[str, Any]] = []

        for supplemental in supplemental_events:
            if not isinstance(supplemental, dict):
                continue
            if any(
                cls._events_equivalent(existing, supplemental, team_id)
                for existing in events
            ):
                continue
            events.append(supplemental)
            added.append(supplemental)

        events.sort(key=lambda event: str(event.get("date") or "9999-12-31T23:59:59Z"))
        data["events"] = events
        result["data"] = data
        return result, added
