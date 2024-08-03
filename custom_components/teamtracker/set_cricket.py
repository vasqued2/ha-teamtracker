""" Cricket specific functionality"""

import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_set_cricket_values(
    new_values, event, competition_index, team_index, lang, sensor_name
) -> bool:
    """Set cricket specific values"""

    oppo_index = 1 - team_index
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        _LOGGER.debug("%s: async_set_cricket_values() 0: %s", sensor_name, sensor_name)
        return False

    new_values["odds"] = await async_get_value(competition, "class", "generalClassCard")
    new_values["clock"] = await async_get_value(
        competition, "status", "type", "description"
    )
    new_values["quarter"] = await async_get_value(competition, "status", "session")

    if await async_get_value(competitor, "linescores", -1, "isBatting"):
        new_values["possession"] = await async_get_value(competitor, "id")
    if await async_get_value(opponent, "linescores", -1, "isBatting"):
        new_values["possession"] = await async_get_value(opponent, "id")

    new_values["last_play"] = await async_get_value(competition, "status", "summary")

    return True
