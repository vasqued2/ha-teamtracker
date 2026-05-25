""" Parse CFL Scoreboard JSON response """
from __future__ import annotations

import logging
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

        # Populate the league_name from derived_league_name if stored, else use season
        self._values.league_name = provider_response.get("lookups", {}).get("derived_league_name", "")
        if self._values.league_name == "" and self._values.season:
            self._values.league_name = season_slug_to_name(self._values.season)

        return rc