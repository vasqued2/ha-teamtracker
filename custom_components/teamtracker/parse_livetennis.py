""" Parse Live Tennis API response """
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .const import TENNIS
from .parse_espn import EspnParser

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class LiveTennisParser(EspnParser):
    """The Live Tennis provider returns the same JSON structure as ESPN."""

    #
    #  initialize_values()
    #    Set sensor attributes that do not rely on the API
    #
    def initialize_sensor_values(self, provider_response) -> bool:
        rc = super().initialize_sensor_values(provider_response)
        self._values.sport = TENNIS

        return rc
