import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)

async def async_set_mma_values(old_values, event, competition, competitor, lang, index, comp_index, sensor_name) -> dict:
        new_values = {}

#        _LOGGER.debug("%s: async_set_mma_values() 100: %s", sensor_name, type(competition))

        if index == 0:
            oppo_index = 1
        else:
            oppo_index = 0

        new_values["state"] = await async_get_value(competition, "status", "type", "state")
#        _LOGGER.debug("%s: async_set_mma_values() 0.1: %s", sensor_name, new_values)

        if new_values["state"] == None:
            new_values["state"] = await async_get_value(event, "status", "type", "state")
        new_values["state"] = new_values["state"].upper()

        t = 0
        o = 0
        for ls in range(0, len(await async_get_value(competitor, "linescores", -1, "linescores", default=[]))):
            if (await async_get_value(competitor, "linescores", -1, "linescores", ls, "value", default=0) > await async_get_value(competition, "competitors", oppo_index, "linescores", -1, "linescores", ls, "value", default=0)):
                t = t + 1
            if (await async_get_value(competitor, "linescores", -1, "linescores", ls, "value", default=0) < await async_get_value(competition, "competitors", oppo_index, "linescores", -1, "linescores", ls, "value", default=0)):
                o = o + 1
            
            new_values["team_score"] = t
            new_values["opponent_score"] = o
        if t == o:
            if await async_get_value(competitor, "winner", default=False) == True:
                new_values["team_score"] = "W"
                new_values["opponent_score"] = "L"
            if await async_get_value(competition, "competitors", oppo_index, "winner", default=False) == True:
                new_values["team_score"] = "L"
                new_values["opponent_score"] = "W"

#        new_values["last_play"] = await async_get_prior_fights(event)

        return(new_values)


async def async_get_prior_fights(event) -> str:
    prior_fights = ""

    c = 1
    for competition in await async_get_value(event, "competitions", default=[]):
        if await async_get_value(competition, "status", "type", "state", default="NOT_FOUND").upper() == "POST":
            prior_fights = prior_fights + str(c) + ". "
            if await async_get_value(competition, "competitors", 0, "winner", default=False):
                prior_fights = prior_fights + "*" + await async_get_value(competition, "competitors", 0, "athlete", "shortName", default="Unknown").upper()
            else:
                prior_fights = prior_fights + await async_get_value(competition, "competitors", 0, "athlete", "shortName", default="Unknown")
            prior_fights = prior_fights + " v. "
            if await async_get_value(competition, "competitors", 1, "winner", default=False):
                prior_fights = prior_fights + await async_get_value(competition, "competitors", 1, "athlete", "shortName", default="Unknown").upper() + "*"
            else:
                prior_fights = prior_fights + await async_get_value(competition, "competitors", 1, "athlete", "shortName", default="Unknown")
            f1 = 0
            f2 = 0
            t = 0
            for ls in range(0, len(await async_get_value(competition, "competitors", 0, "linescores", 0, "linescores", default=[]))):
                if await async_get_value(competition, "competitors", 0, "linescores", 0, "linescores", ls, "value", default=0) > await async_get_value(competition, "competitors", 1, "linescores", 0, "linescores", ls, "value", default=0):
                    f1= f1 + 1
                elif (await async_get_value(competition, "competitors", 0, "linescores", 0, "linescores", ls, "value", default=0) < await async_get_value(competition, "competitors", 1, "linescores", 0, "linescores", ls, "value", default=0)):
                    f2 = f2 + 1
                else:
                    t = t + 1

            prior_fights = prior_fights + " (Dec: " + str(f1) + "-" + str(f2)
            if t != 0:
                prior_fights = prior_fights + "-" + str(t)
            prior_fights = prior_fights + ") "
            if (f1 == 0 and f2 ==0 and t == 0):
                prior_fights = prior_fights + " (KO/TKO/Sub: R" + str(await get_value(competition, "status", "period", default="?")) + "@" + str(await async_get_value(competition, "status", "displayClock", default="0:00")) + ") "
                    
            prior_fights = prior_fights + "; "
            c = c + 1
    return prior_fights