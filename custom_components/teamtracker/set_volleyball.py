""" Volleyball specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)

class SetVolleyballMixin:
    _sensor_name: str
    _values: TeamTrackerValues

    async def _async_set_volleyball_values(
        self, 
        event, competition_index, team_index
    ) -> bool:
        """Set volleyball specific values"""

        oppo_index = 1 - team_index
        competition = await async_get_value(event, "competitions", competition_index)
        competitor = await async_get_value(competition, "competitors", team_index)
        opponent = await async_get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            _LOGGER.debug(
                "%s: async_set_volleyball_values() 0: %s", self._sensor_name, self._sensor_name
            )
            return False

        self._values.clock = await async_get_value(
            event, "status", "type", "detail"
        )  # Set
        self._values.team_sets_won = self._values.team_score
        self._values.opponent_sets_won = self._values.opponent_score

        if self._values.state == "IN":
            self._values.team_score = await async_get_value(
                competitor, "linescores", -1, "value", default=0
            )
            self._values.opponent_score = await async_get_value(
                opponent, "linescores", -1, "value", default=0
            )

        last_play = ""
        linescores = await async_get_value(competitor, "linescores", default=[])
        sets_count = len(linescores)

        for x in range(0, sets_count):
            t_val = int(await async_get_value(competitor, "linescores", x, "value", default=0))
            o_val = int(await async_get_value(opponent, "linescores", x, "value", default=0))
            
            last_play += f" Set {x + 1}: {self._values.team_abbr} {t_val} {self._values.opponent_abbr} {o_val}; "

        self._values.last_play = last_play

        return True