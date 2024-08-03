""" Volleyball specific functionality"""

import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_set_volleyball_values(
    new_values, event, competition_index, team_index, sensor_name
) -> bool:
    """Set volleyball specific values"""

    oppo_index = 1 - team_index
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        _LOGGER.debug(
            "%s: async_set_volleyball_values() 0: %s", sensor_name, sensor_name
        )
        return False

    new_values["clock"] = await async_get_value(
        event, "status", "type", "detail"
    )  # Set
    new_values["team_sets_won"] = new_values["team_score"]
    new_values["opponent_sets_won"] = new_values["opponent_score"]

    if new_values["state"] == "IN":
        new_values["team_score"] = await async_get_value(
            competitor, "linescores", -1, "value", default=0
        )
        new_values["opponent_score"] = await async_get_value(
            opponent, "linescores", -1, "value", default=0
        )

    new_values["last_play"] = ""
    sets = len(await async_get_value(competitor, "linescores", default=[]))

    for x in range(0, sets):
        new_values["last_play"] = new_values["last_play"] + " Set " + str(x + 1) + ": "
        new_values["last_play"] = (
            new_values["last_play"] + new_values["team_abbr"] + " "
        )
        new_values["last_play"] = (
            new_values["last_play"]
            + str(
                int(
                    await async_get_value(
                        competitor, "linescores", x, "value", default=0
                    )
                )
            )
            + " "
        )
        new_values["last_play"] = (
            new_values["last_play"] + new_values["opponent_abbr"] + " "
        )
        new_values["last_play"] = (
            new_values["last_play"]
            + str(
                int(
                    await async_get_value(opponent, "linescores", x, "value", default=0)
                )
            )
            + "; "
        )
    return True
