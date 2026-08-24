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

        # Prefer the league name derived from the matched event's own season
        # slug: it is always fresh, since it comes from the same scoreboard
        # response that matched this game. derived_league_name, by contrast,
        # comes from a separately cached team-schedule lookup that is not
        # tied to the specific matched event (see _async_get_team_schedule
        # in provide_espn_all.py) and can end up describing a different
        # competition than the one currently being displayed - e.g. a
        # friendly instead of the actual league match.
        self._values.league_name = ""
        if self._values.season:
            self._values.league_name = season_slug_to_name(self._values.season)
        if self._values.league_name == "":
            self._values.league_name = provider_response.get("lookups", {}).get("derived_league_name", "")

        return rc