""" Racing specific functionality"""

import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_set_racing_values(
    new_values, event, competition_index, team_index, lang, sensor_name
) -> bool:
    """Set racing specific values"""

    #    _LOGGER.debug("%s: async_set_racing_values() 0: %s", sensor_name, new_values)

    if team_index == 0:
        oppo_index = 1
    else:
        oppo_index = 0
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        _LOGGER.debug("%s: async_set_racing_values() 0: %s", sensor_name, sensor_name)
        return False

    city = await async_get_value(event, "circuit", "address", "city")
    country = await async_get_value(event, "circuit", "address", "country")
    #    _LOGGER.debug("%s: async_set_racing_values() 1: %s", sensor_name, new_values)

    if city is not None:
        new_values["location"] = "%s, %s" % (city, country)
    else:
        new_values["location"] = country

    new_values["team_score"] = team_index + 1
    new_values["opponent_score"] = oppo_index + 1
    #    _LOGGER.debug("%s: async_set_racing_values() 2: %s", sensor_name, new_values)

    if new_values["state"] == "PRE":
        new_values["team_rank"] = team_index + 1
        new_values["opponent_rank"] = oppo_index + 1
    #    _LOGGER.debug("%s: async_set_racing_values() 3: %s", sensor_name, new_values)

    new_values["team_total_shots"] = await async_get_value(
        competition, "status", "period"
    )
    new_values["quarter"] = await async_get_value(competition, "type", "abbreviation")
    #    _LOGGER.debug("%s: async_set_racing_values() 4: %s", sensor_name, new_values)

    new_values["last_play"] = ""
    for x in range(0, 10):
        new_values["last_play"] = (
            new_values["last_play"]
            + str(
                await async_get_value(competition, "competitors", x, "order", default=x)
            )
            + ". "
        )
        new_values["last_play"] = (
            new_values["last_play"]
            + str(
                await async_get_value(
                    competition,
                    "competitors",
                    x,
                    "athlete",
                    "shortName",
                    default="{shortName}",
                )
            )
            + ",   "
        )
    new_values["last_play"] = new_values["last_play"][:-1]

    return True
