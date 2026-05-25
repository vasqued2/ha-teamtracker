""" Parse CFL Scoreboard JSON response """
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .parse_espn import EspnParser

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class HockeyTechParser(EspnParser):
    """The HockeyTech provider returns the same JSON structure as ESPN."""

    #
    #  initialize_values()
    #    Set sensor attributes that do not rely on the API
    #
    def initialize_sensor_values(self, provider_response) -> bool:
        rc = super().initialize_sensor_values(provider_response)
        self._values.sport = "hockey"

        return rc