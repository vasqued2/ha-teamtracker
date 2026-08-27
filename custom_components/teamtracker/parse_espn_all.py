""" Parse CFL Scoreboard JSON response """
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .parse_espn import EspnParser
from .utils import get_value, season_slug_to_name

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class EspnAllParser(EspnParser):
    """The Espn All provider returns the same JSON structure as ESPN."""

    #
    #  _set_universal_values()
    #    Also capture altGameNote from the matched competition, ESPN's own
    #    human-readable label for it (e.g. "English Premier League",
    #    "LALIGA", "Carabao Cup, Second Round"). Only needed for "all"
    #    league sensors, so it's captured here rather than in the shared
    #    SetValuesMixin. Must happen in the same step as self._values.season
    #    (not later, e.g. in finalize_sensor_values) so it participates
    #    correctly in the prev-values revert logic in process_name_match().
    #
    def _set_universal_values(
        self, event, grouping_index, competition_index, team_index
    ) -> bool:
        rc = super()._set_universal_values(
            event, grouping_index, competition_index, team_index
        )
        if rc:
            grouping = get_value(event, "groupings", grouping_index)
            if grouping is None:
                competition = get_value(event, "competitions", competition_index)
            else:
                competition = get_value(grouping, "competitions", competition_index)
            self._values.alt_game_note = get_value(competition, "altGameNote")

        return rc


    #
    #  finalize_sensor_values()
    #    Set sensor attributes that do not rely on the API
    #
    def finalize_sensor_values(self, provider_response) -> bool:
        rc = super().finalize_sensor_values(provider_response)

        # Determine league_name from data tied to the matched event itself -
        # never from derived_league_name, which comes from a separately
        # cached team-schedule lookup that isn't tied to the specific
        # matched event (see _async_get_team_schedule in
        # provide_espn_all.py) and can end up describing a different
        # competition than the one currently being displayed - e.g. a
        # friendly instead of the actual league or cup match.
        #
        # 1. altGameNote: preferred because it already covers cases the
        #    season slug can't, such as cup rounds whose slug is just
        #    "second-round" with no competition name in it.
        # 2. The matched event's own season slug, converted to a name.
        #    Also always fresh, just less descriptive for cup rounds.
        # 3. derived_league_name, only as a last resort.
        #
        # Fields default to the TeamTrackerValues MISSING sentinel (a plain
        # truthy object) until a match is found and _set_universal_values()
        # sets them, so guard with isinstance rather than plain truthiness.
        alt_game_note = self._values.alt_game_note
        season = self._values.season
        alt_game_note = alt_game_note if isinstance(alt_game_note, str) else None
        season = season if isinstance(season, str) else None

        self._values.league_name = alt_game_note or ""
        if self._values.league_name == "" and season:
            self._values.league_name = season_slug_to_name(season)
        if self._values.league_name == "":
            self._values.league_name = provider_response.get("lookups", {}).get("derived_league_name", "")

        return rc