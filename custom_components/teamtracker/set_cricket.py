""" Cricket specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import get_value

_LOGGER = logging.getLogger(__name__)

class SetCricketMixin:
    _sensor_name: str
    _values: TeamTrackerValues

    def _set_cricket_values(
        self,
        event, competition_index, team_index
    ) -> bool:
        """Set cricket specific values"""

        oppo_index = 1 - team_index
        competition = get_value(event, "competitions", competition_index)
        competitor = get_value(competition, "competitors", team_index)
        opponent = get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            _LOGGER.debug("%s: async_set_cricket_values() 0: %s", self._sensor_name, self._sensor_name)
            return False

        self._values.odds = get_value(competition, "class", "generalClassCard")
        self._values.clock = get_value(
            competition, "status", "type", "description"
        )
        self._values.quarter = get_value(competition, "status", "session")

        if get_value(competitor, "linescores", -1, "isBatting"):
            self._values.possession = get_value(competitor, "id")
        if get_value(opponent, "linescores", -1, "isBatting"):
            self._values.possession = get_value(opponent, "id")

        self._values.last_play = get_value(competition, "status", "summary")

        return True