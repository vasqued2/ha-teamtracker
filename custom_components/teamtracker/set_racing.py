""" Racing specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)
race_laps: dict[str, int] = {}

class SetRacingMixin:
    _sensor_name: str
    _values: TeamTrackerValues

    
    async def _async_set_racing_values(
        self,
        event, competition_index, team_index
    ) -> bool:
        """Set racing specific values"""

        #    _LOGGER.debug("%s: async_set_racing_values() 0: %s", self._sensor_name, new_values)

        oppo_index = 1 if team_index == 0 else 0
        competition = await async_get_value(event, "competitions", competition_index)
        competitor = await async_get_value(competition, "competitors", team_index)
        opponent = await async_get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            _LOGGER.debug("%s: async_set_racing_values() 0: %s", self._sensor_name, self._sensor_name)
            return False

        city = await async_get_value(event, "circuit", "address", "city")
        country = await async_get_value(event, "circuit", "address", "country")
        #    _LOGGER.debug("%s: async_set_racing_values() 1: %s", self._sensor_name, new_values)

        if city is not None:
            self._values.location = f"{city}, {country}"
        else:
            self._values.location = country

        self._values.team_score = str(team_index + 1)
        self._values.opponent_score = str(oppo_index + 1)
        #     _LOGGER.debug("%s: async_set_racing_values() 2: %s", self._sensor_name, new_values)

        if self._values.state == "PRE":
            self._values.team_rank = str(team_index + 1)
            self._values.opponent_rank = str(oppo_index + 1)
        #    _LOGGER.debug("%s: async_set_racing_values() 3: %s", self._sensor_name, new_values)

        # Use team_total_shots to track laps; logic remains consistent with original global usage
        self._values.team_total_shots = await async_get_value(
            competition, "status", "period",
            default=self._values.team_total_shots,
        )

        self._values.quarter = await async_get_value(competition, "type", "abbreviation")
        #     _LOGGER.debug("%s: async_set_racing_values() 4: %s", self._sensor_name, new_values)

        last_play = ""
        for x in range(0, 10):
            last_play += str(
                    await async_get_value(competition, "competitors", x, "order", default=x)
                ) + ". "
            last_play += str(
                    await async_get_value(
                        competition,
                        "competitors",
                        x,
                        "athlete",
                        "shortName",
                        default="{shortName}",
                    )
                ) + ",   "
        
        self._values.last_play = last_play[:-1]

        return True