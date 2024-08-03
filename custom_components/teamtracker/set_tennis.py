""" Tennis specific functionality"""

import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_set_tennis_values(
    new_values, event, grouping_index, competition_index, team_index, lang, sensor_name
) -> bool:
    """Set tennis specific values"""

    #    _LOGGER.debug("%s: async_set_tennis_values() 0: %s %s %s", sensor_name, sensor_name, grouping_index, competition_index)

    oppo_index = 1 - team_index
        
    grouping = await async_get_value(event, "groupings", grouping_index)
    if grouping is None:
        competition = await async_get_value(event, "competitions", competition_index)
    else:
        competition = await async_get_value(grouping, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        #        _LOGGER.debug("%s: async_set_tennis_values() 0.1: %s", sensor_name, sensor_name)
        return False

#    remaining_games = (
#        len(await async_get_value(event, "competitions", default=[]))
#        - competition_index
#    )
#    new_values["odds"] = 1 << remaining_games.bit_length()  # Game is in the round of X
#    #    _LOGGER.debug("%s: async_set_tennis_values() 1: %s %s %s", sensor_name, remaining_games, len(event["competitions"]), competition_index)

    new_values["location"] = await async_get_value(
        competition,
        "venue",
        "court"
    )
    new_values["down_distance_text"] = await async_get_value(
        competition,
        "round",
        "displayName"
    )
    new_values["overunder"] = await async_get_value(
        competition,
        "type",
        "text"
    )
    new_values["team_rank"] = await async_get_value(competitor, "tournamentSeed")
    new_values["opponent_rank"] = await async_get_value(opponent, "tournamentSeed")

    new_values["clock"] = await async_get_value(
        competition,
        "status",
        "type",
        "detail",
        default=await async_get_value(event, "status", "type", "shortDetail"),
    )

    #    _LOGGER.debug("%s: async_set_tennis_values() 2: %s", sensor_name, sensor_name)

    new_values["team_score"] = await async_get_value(competitor, "score")
    #    _LOGGER.debug("%s: async_set_tennis_values() 3: %s", sensor_name, sensor_name)

    new_values["opponent_score"] = await async_get_value(opponent, "score")
    #    _LOGGER.debug("%s: async_set_tennis_values() 4: %s", sensor_name, sensor_name)

    new_values["team_score"] = await async_get_value(
        competitor, "linescores", -1, "value"
    )
    #    _LOGGER.debug("%s: async_set_tennis_values() 5: %s", sensor_name, sensor_name)
    new_values["opponent_score"] = await async_get_value(
        opponent, "linescores", -1, "value"
    )
    #    _LOGGER.debug("%s: async_set_tennis_values() 5.1: %s", sensor_name, sensor_name)
    new_values["team_shots_on_target"] = await async_get_value(
        competitor, "linescores", -1, "tiebreak"
    )
    #    _LOGGER.debug("%s: async_set_tennis_values() 5.2: %s", sensor_name, sensor_name)
    new_values["opponent_shots_on_target"] = await async_get_value(
        opponent, "linescores", -1, "tiebreak"
    )

    #    _LOGGER.debug("%s: async_set_tennis_values() 6: %s", sensor_name, sensor_name)

    if new_values["state"] == "POST":
        new_values["team_score"] = 0
        new_values["opponent_score"] = 0
        #        _LOGGER.debug("%s: async_set_tennis_values() 6.1: %s", sensor_name, sensor_name)

        for x in range(
            0, len(await async_get_value(competitor, "linescores", default=[]))
        ):
            if int(
                await async_get_value(competitor, "linescores", x, "value", default=0)
            ) > int(
                await async_get_value(opponent, "linescores", x, "value", default=0)
            ):
                new_values["team_score"] = new_values["team_score"] + 1
            else:
                new_values["opponent_score"] = new_values["opponent_score"] + 1

    new_values["last_play"] = ""
    #    _LOGGER.debug("%s: async_set_tennis_values() 7: %s", sensor_name, await async_get_value(competitor, "linescores"))
    sets = len(await async_get_value(competitor, "linescores", default=[]))

    #    _LOGGER.debug("%s: async_set_tennis_values() 8: %s", sensor_name, sets)

    for x in range(0, sets):
        new_values["last_play"] = new_values["last_play"] + " Set " + str(x + 1) + ": "
        new_values["last_play"] = (
            new_values["last_play"]
            + str(
                await async_get_value(competitor, "athlete", "shortName", 
                        default=await async_get_value(competitor, "roster", "shortDisplayName", 
                            default="{shortName}")
                )
            )
            + " "
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
            new_values["last_play"]
            + str(
                await async_get_value(opponent, "athlete", "shortName",
                        default=await async_get_value(opponent, "roster", "shortDisplayName", 
                            default="{shortName}")
                )
            )
            + " "
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

    new_values["team_sets_won"] = 0
    new_values["opponent_sets_won"] = 0
    for x in range(0, sets - 1):
        if await async_get_value(
            competitor, "linescores", x, "value", default=0
        ) > await async_get_value(opponent, "linescores", x, "value", default=0):
            new_values["team_sets_won"] = new_values["team_sets_won"] + 1
        else:
            new_values["opponent_sets_won"] = new_values["opponent_sets_won"] + 1

    #    _LOGGER.debug("%s: async_set_tennis_values() 9: %s", sensor_name, new_values)

    return True
