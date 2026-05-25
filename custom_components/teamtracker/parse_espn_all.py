""" Parse CFL Scoreboard JSON response """
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from .parse_espn import EspnParser
from .utils import season_slug_to_name

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class EspnAllParser(EspnParser):
    """The Espn All provider returns the same JSON structure as ESPN."""

    #
    #  finalize_sensor_values()
    #    Set sensor attributes that do not rely on the API
    #
    def finalize_sensor_values(self, provider_response) -> bool:
        rc = super().finalize_sensor_values(provider_response)

        # Populate the league_name from the lookup or the season name
        competition = provider_response.get("lookups", {}).get("derived_league_name", "")
        self._values.league_name = re.sub(r"^\d{4}(-\d{2})?\s+", "", competition)

        if self._values.league_name == "" and self._values.season:
            self._values.league_name = season_slug_to_name(self._values.season)

        return rc