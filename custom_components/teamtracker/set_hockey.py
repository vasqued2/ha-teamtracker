""" Hockey specific functionality"""

import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_set_hockey_values(
    new_values, event, competition_index, team_index, sensor_name
) -> bool:
    """Set hockey specific values"""

    oppo_index = 1 - team_index
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        _LOGGER.debug("%s: async_set_hockey_values() 0: %s", sensor_name, sensor_name)
        return False

    #    new_values["clock"] = await async_get_value(event, "status", "type", "shortDetail") # Period clock

    new_values["team_shots_on_target"] = 0
    for statistic in await async_get_value(opponent, "statistics", default=[]):
        if "saves" in await async_get_value(statistic, "name", default=[]):
            shots = int(new_values["team_score"]) + int(
                await async_get_value(statistic, "displayValue", default=0)
            )
            new_values["team_shots_on_target"] = str(shots)

    new_values["opponent_shots_on_target"] = 0
    for statistic in await async_get_value(competitor, "statistics", default=[]):
        if "saves" in await async_get_value(statistic, "name", default=[]):
            shots = int(new_values["opponent_score"]) + int(
                await async_get_value(statistic, "displayValue", default=0)
            )
            new_values["opponent_shots_on_target"] = str(shots)

    return True
