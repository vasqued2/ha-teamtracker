""" Golf specific functionality"""

import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_set_golf_values(
    new_values, event, competition_index, team_index, lang, sensor_name
) -> bool:
    """Set golf specific values"""

    oppo_index = 1 if team_index == 0 else 0
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        #        _LOGGER.debug("%s: async_set_golf_values() 0: %s", sensor_name, sensor_name)
        return False

    #    _LOGGER.debug("%s: async_set_golf_values() 1: %s %s %s", sensor_name, competition_index, team_index, oppo_index)

    if new_values["state"] in ["IN", "POST"]:
        #       _LOGGER.debug("%s: async_set_golf_values() 1.1: %s", sensor_name, sensor_name)

        new_values["team_rank"] = await async_get_golf_position(competition, team_index)
        new_values["opponent_rank"] = await async_get_golf_position(
            competition, oppo_index
        )
    else:
        #       _LOGGER.debug("%s: async_set_golf_values() 1.2: %s", sensor_name, sensor_name)
        new_values["team_rank"] = None
        new_values["opponent_rank"] = None

    #    _LOGGER.debug("%s: async_set_golf_values() 1.3: %s", sensor_name, new_values)

    if new_values["state"] in ["IN", "POST"]:
        golf_round = new_values["quarter"] - 1
        #        _LOGGER.debug("%s: async_set_golf_values() 2: %s", sensor_name, golf_round)

        new_values["team_total_shots"] = await async_get_value(
            competitor, "linescores", golf_round, "value", default=0
        )
        new_values["team_shots_on_target"] = len(
            await async_get_value(
                competitor, "linescores", golf_round, "linescores", default=[]
            )
        )
        new_values["opponent_total_shots"] = await async_get_value(
            opponent, "linescores", golf_round, "value", default=0
        )
        new_values["opponent_shots_on_target"] = len(
            await async_get_value(
                opponent, "linescores", golf_round, "linescores", default=[]
            )
        )

        #        _LOGGER.debug("%s: async_set_golf_values() 3: %s", sensor_name, golf_round)

        new_values["last_play"] = ""
        for x in range(0, 10):
            p = await async_get_golf_position(competition, x)
            new_values["last_play"] = new_values["last_play"] + p + ". "
            new_values["last_play"] = new_values["last_play"] + await async_get_value(
                competition, "competitors", x, "athlete", "shortName"
            )
            new_values["last_play"] = (
                new_values["last_play"]
                + " ("
                + str(
                    await async_get_value(
                        competition, "competitors", x, "score", default=""
                    )
                )
                + "),   "
            )

        #        _LOGGER.debug("%s: async_set_golf_values() 4: %s", sensor_name, new_values)
        new_values["last_play"] = new_values["last_play"][:-1]

    return True


async def async_get_golf_position(competition, index) -> str:
    """Determine the position of index considering ties if score matches leading or trailing position"""

    t = 0
    tie = ""
    for x in range(1, index + 1):
        if await async_get_value(
            competition, "competitors", x, "score", default=1000
        ) == await async_get_value(
            competition, "competitors", t, "score", default=1001
        ):
            tie = "T"
        else:
            tie = ""
            t = x
    if await async_get_value(
        competition, "competitors", index, "score", default=1000
    ) == await async_get_value(
        competition, "competitors", index + 1, "score", default=1001
    ):
        tie = "T"

    return tie + str(t + 1)
