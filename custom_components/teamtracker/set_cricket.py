""" Cricket specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)

class SetCricketMixin:
    _sensor_name: str

    async def _async_set_cricket_values(
        self,
        new_values, event, competition_index, team_index
    ) -> bool:
        """Set cricket specific values"""

        self._values = TeamTrackerValues.from_dict(new_values)

        oppo_index = 1 - team_index
        competition = await async_get_value(event, "competitions", competition_index)
        competitor = await async_get_value(competition, "competitors", team_index)
        opponent = await async_get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            _LOGGER.debug("%s: async_set_cricket_values() 0: %s", self._sensor_name, self._sensor_name)
            return False

        self._values.odds = await async_get_value(competition, "class", "generalClassCard")
        self._values.clock = await async_get_value(
            competition, "status", "type", "description"
        )
        self._values.quarter = await async_get_value(competition, "status", "session")

        if await async_get_value(competitor, "linescores", -1, "isBatting"):
            self._values.possession = await async_get_value(competitor, "id")
        if await async_get_value(opponent, "linescores", -1, "isBatting"):
            self._values.possession = await async_get_value(opponent, "id")

        self._values.last_play = await async_get_value(competition, "status", "summary")

        new_values.update(self._values.to_dict())
        
        return True