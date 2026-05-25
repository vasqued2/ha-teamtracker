""" Soccer specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import get_value

_LOGGER = logging.getLogger(__name__)

class SetSoccerMixin:
    _sensor_name: str
    _values: TeamTrackerValues


    async def _async_set_soccer_values(
        self,
        event, competition_index, team_index
    ) -> bool:
        """Set soccer specific values"""

        teamPP = None
        oppoPP = None

        oppo_index = 1 - team_index
        competition = get_value(event, "competitions", competition_index)
        competitor = get_value(competition, "competitors", team_index)
        opponent = get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            _LOGGER.debug("%s: async_set_soccer_values() 0: %s", self._sensor_name, self._sensor_name)
            return False

        #     _LOGGER.debug("%s: async_set_soccer_values() 1: %s", self._sensor_name, self._sensor_name)

        self._values.team_shots_on_target = 0
        self._values.team_total_shots = 0
        for statistic in get_value(competitor, "statistics", default=[]):
            stat_name = get_value(statistic, "name", default="")
            if "shotsOnTarget" in stat_name:
                self._values.team_shots_on_target = get_value(statistic, "displayValue")
            if "totalShots" in stat_name:
                self._values.team_total_shots = get_value(statistic, "displayValue")
            if "possessionPct" in stat_name:
                teamPP = get_value(statistic, "displayValue")

        #     _LOGGER.debug("%s: async_set_soccer_values() 2: %s", self._sensor_name, self._sensor_name)

        self._values.opponent_shots_on_target = 0
        self._values.opponent_total_shots = 0
        for statistic in get_value(opponent, "statistics", default=[]):
            stat_name = get_value(statistic, "name", default="")
            if "shotsOnTarget" in stat_name:
                self._values.opponent_shots_on_target = get_value(statistic, "displayValue")
            if "totalShots" in stat_name:
                self._values.opponent_total_shots = get_value(statistic, "displayValue")
            if "possessionPct" in stat_name:
                oppoPP = get_value(statistic, "displayValue")

        #     _LOGGER.debug("%s: async_set_soccer_values() 3: %s", self._sensor_name, self._sensor_name)

        last_play = ""
        if teamPP and oppoPP:
            last_play = (
                f"{self._values.team_abbr} {teamPP}%, {self._values.opponent_abbr} {oppoPP}%; "
            )

        for detail in get_value(event, "competitions", 0, "details", default=[]):
            try:
                mls_team_id = get_value(detail, "team", "id", default=0)
                clock = get_value(detail, "clock", "displayValue", default="{clock}")
                event_type = get_value(detail, "type", "text", default="{type}")
                athlete = get_value(detail, "athletesInvolved", 0, "displayName", default="{displayName}")

                last_play += f"     {clock}  {event_type}: {athlete}"

                if mls_team_id == self._values.team_id:
                    last_play += f" ({self._values.team_abbr})"
                else:
                    last_play += f" ({self._values.opponent_abbr})          "
            except:
                last_play += " {last_play} "

        self._values.last_play = last_play

        return True