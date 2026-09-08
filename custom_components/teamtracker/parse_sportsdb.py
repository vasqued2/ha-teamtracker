"""Parse TheSportsDB provider responses."""

from __future__ import annotations

import re

from .parse_espn_all import EspnAllParser
from .utils import get_value


class SportsDbParser(EspnAllParser):
    """Parse TheSportsDB data transformed to TeamTracker's ESPN contract."""

    _SPORT_MAP = {
        "american football": "football",
        "australian football": "australian-football",
        "baseball": "baseball",
        "basketball": "basketball",
        "cricket": "cricket",
        "golf": "golf",
        "ice hockey": "hockey",
        "hockey": "hockey",
        "mma": "mma",
        "mixed martial arts": "mma",
        "motorsport": "racing",
        "motor sport": "racing",
        "rugby": "rugby",
        "soccer": "soccer",
        "tennis": "tennis",
        "volleyball": "volleyball",
    }

    def initialize_sensor_values(self, provider_response) -> bool:
        """Initialize values and expose the provider's actual sport."""
        rc = super().initialize_sensor_values(provider_response)

        sport = provider_response.get("lookups", {}).get(
            "sportsdb_sport", ""
        )
        if sport:
            self._values.sport = self._normalize_sport_name(str(sport))

        return rc

    def _set_universal_values(
        self,
        event,
        grouping_index,
        competition_index,
        team_index,
    ) -> bool:
        """Capture matched-event league metadata from TheSportsDB."""
        rc = super()._set_universal_values(
            event,
            grouping_index,
            competition_index,
            team_index,
        )

        if not rc:
            return rc

        grouping = get_value(event, "groupings", grouping_index)
        if grouping is None:
            competition = get_value(
                event, "competitions", competition_index
            )
        else:
            competition = get_value(
                grouping, "competitions", competition_index
            )

        league_logo = get_value(competition, "leagueLogo")
        if league_logo:
            self._values.league_logo = league_logo

        league_id = get_value(competition, "leagueId")
        if league_id:
            self._values.league = str(league_id)

        return rc

    @classmethod
    def _normalize_sport_name(cls, sport: str) -> str:
        """Map TheSportsDB sport names to TeamTracker sport identifiers."""
        normalized = sport.strip().lower()
        if normalized in cls._SPORT_MAP:
            return cls._SPORT_MAP[normalized]

        return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
