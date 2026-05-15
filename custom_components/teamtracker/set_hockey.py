""" Hockey specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import async_get_value, is_integer

_LOGGER = logging.getLogger(__name__)

class SetHockeyMixin:
    _sensor_name: str
    _values: TeamTrackerValues

    async def _async_set_hockey_values(
        self,
        event, competition_index, team_index
    ) -> bool:
        """Set hockey specific values"""

        oppo_index = 1 - team_index
        competition = await async_get_value(event, "competitions", competition_index)
        competitor = await async_get_value(competition, "competitors", team_index)
        opponent = await async_get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            _LOGGER.debug("%s: async_set_hockey_values() 0: %s", self._sensor_name, self._sensor_name)
            return False

        #     new_values["clock"] = await async_get_value(event, "status", "type", "shortDetail") # Period clock

        self._values.team_shots_on_target = 0
        for statistic in await async_get_value(opponent, "statistics", default=[]):
            if "saves" in await async_get_value(statistic, "name", default=[]):
                if self._values.team_score and is_integer(self._values.team_score):
                    score = int(self._values.team_score)
                else:
                    score = 0
                shots = score + int(
                    await async_get_value(statistic, "displayValue", default=0)
                )
                self._values.team_shots_on_target = shots

        self._values.opponent_shots_on_target = 0
        for statistic in await async_get_value(competitor, "statistics", default=[]):
            if "saves" in await async_get_value(statistic, "name", default=[]):
                if self._values.opponent_score and is_integer(self._values.opponent_score):
                    score = int(self._values.opponent_score)
                else:
                    score = 0

                shots = score + int(
                    await async_get_value(statistic, "displayValue", default=0)
                )
                self._values.opponent_shots_on_target = shots

        return True