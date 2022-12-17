import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)

async def async_set_golf_values(old_values, event, competition, competitor, lang, index, comp_index, sensor_name) -> dict:
        new_values = {}

#        _LOGGER.debug("%s: async_set_golf_values() 0: %s", sensor_name, type(competition))

        if index == 0:
            oppo_index = 1
        else:
            oppo_index = 0

        new_values["state"] = await async_get_value(competition, "status", "type", "state")
#        _LOGGER.debug("%s: async_set_golf_values() 0.1: %s", sensor_name, new_values)

        if new_values["state"] == None:
            new_values["state"] = await async_get_value(event, "status", "type", "state")
        new_values["state"] = new_values["state"].upper()
        new_values["quarter"] = await async_get_value(competition, "status", "period")

#        _LOGGER.debug("%s: async_set_golf_values() 0.2: %s", sensor_name, new_values)

        if new_values["state"] == None:
            new_values["state"] = await async_get_value(event, "status", "type", "state")
        new_values["state"] = new_values["state"].upper()

#        _LOGGER.debug("%s: async_set_golf_values() 1: %s", sensor_name, new_values)


        if new_values["state"] in ["IN","POST"]:
            new_values["team_rank"] = await async_get_golf_position(competition, index)
            new_values["opponent_rank"] = await async_get_golf_position(competition, oppo_index)
        else:
            new_values["team_rank"] = None
            new_values["opponent_rank"] = None

        round = new_values["quarter"] - 1

        new_values["team_total_shots"] = await async_get_value(competitor, "linescores", round, "value", 
                                                    default=0)
        new_values["team_shots_on_target"] = len(await async_get_value(competitor, "linescores", round, "linescores", 
                                                    default=[]))
        new_values["opponent_total_shots"] = await async_get_value(competition, "competitors", oppo_index, "linescores", round, "value",
                                                    default=0)
        new_values["opponent_shots_on_target"] = len(await async_get_value(competition, "competitors", oppo_index, "linescores", round, "linescores",
                                                    default=[]))

        new_values["last_play"] = ""
        for x in range (0, 10):
            p = await async_get_golf_position(competition, x)
            new_values["last_play"] = new_values["last_play"] + p + ". "
            new_values["last_play"] = new_values["last_play"] + await async_get_value(competition, "competitors", x, "athlete", "shortName")
            new_values["last_play"] = new_values["last_play"] + " (" + str(await async_get_value(competition, "competitors", x, "score", default="")) + "),   "

        new_values["last_play"] = new_values["last_play"][:-1]

        return(new_values)


async def async_get_golf_position(competition, index) -> str:

    t = 0
    tie = ""
    for x in range (1, index + 1):
        if await async_get_value(competition, "competitors", x, "score", default=1000) == await async_get_value(competition, "competitors", t, "score", default=1001):
            tie = "T"
        else:
            tie = ""
            t = x
    if await async_get_value(competition, "competitors", index, "score", default=1000) == await async_get_value(competition, "competitors", index + 1, "score", default=1001):
        tie = "T"

    return tie + str(t + 1)