import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)

async def async_set_racing_values(old_values, event, competition, competitor, lang, index, comp_index, sensor_name) -> dict:
        new_values = {}

#        _LOGGER.debug("%s: async_set_racing_values() 1: %s", sensor_name, type(competition))

        if index == 0:
            oppo_index = 1
        else:
            oppo_index = 0

        new_values["state"] = await async_get_value(competition, "status", "type", "state")
#        _LOGGER.debug("%s: async_set_racing_values() 0.1: %s", sensor_name, new_values)

        if new_values["state"] == None:
            new_values["state"] = await async_get_value(event, "status", "type", "state")
        new_values["state"] = new_values["state"].upper()
        
        new_values["venue"] = await async_get_value(event, "circuit", "fullName")
#        _LOGGER.debug("%s: async_set_racing_values() 2: %s", sensor_name, new_values)

        city = await async_get_value(event, "circuit", "address", "city")
        country = await async_get_value(event, "circuit", "address", "country")
        if city != None:
            new_values["location"] = "%s, %s" % (city, country)
        else:
            new_values["location"] = country

        new_values["team_score"] = index + 1
        new_values["opponent_score"] = oppo_index + 1

        if new_values["state"] == "PRE":
            new_values["team_rank"] = index + 1
            new_values["opponent_rank"] = oppo_index + 1
#        _LOGGER.debug("%s: async_set_racing_values() 3: %s", sensor_name, new_values)

        new_values["team_total_shots"] = await async_get_value(competition, "status", "period")
        new_values["quarter"] = await async_get_value(competition, "type", "abbreviation")
#        _LOGGER.debug("%s: async_set_racing_values() 4: %s", sensor_name, new_values)

        new_values["last_play"] = ""
        for x in range (0, 10):
            new_values["last_play"] = new_values["last_play"] + str(await async_get_value(competition, "competitors", x,"order", default=x)) + ". "
            new_values["last_play"] = new_values["last_play"] + str(await async_get_value(competition, "competitors", x, "athlete", "shortName", default="?")) + ",   "
        new_values["last_play"] = new_values["last_play"][:-1]

        return new_values
