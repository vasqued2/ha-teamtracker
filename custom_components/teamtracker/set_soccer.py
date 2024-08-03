""" Soccer specific functionality"""

import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_set_soccer_values(
    new_values, event, competition_index, team_index, sensor_name
) -> bool:
    """Set soccer specific values"""

    teamPP = None
    oppoPP = None

    oppo_index = 1 - team_index
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        _LOGGER.debug("%s: async_set_soccer_values() 0: %s", sensor_name, sensor_name)
        return False

    #    _LOGGER.debug("%s: async_set_soccer_values() 1: %s", sensor_name, sensor_name)

    new_values["team_shots_on_target"] = 0
    new_values["team_total_shots"] = 0
    for statistic in await async_get_value(competitor, "statistics", default=[]):
        if "shotsOnTarget" in await async_get_value(statistic, "name", default=[]):
            new_values["team_shots_on_target"] = await async_get_value(
                statistic, "displayValue"
            )
        if "totalShots" in await async_get_value(statistic, "name", default=[]):
            new_values["team_total_shots"] = await async_get_value(
                statistic, "displayValue"
            )
        if "possessionPct" in await async_get_value(statistic, "name", default=[]):
            teamPP = await async_get_value(statistic, "displayValue")

    #    _LOGGER.debug("%s: async_set_soccer_values() 2: %s", sensor_name, sensor_name)

    new_values["opponent_shots_on_target"] = 0
    new_values["opponent_total_shots"] = 0
    for statistic in await async_get_value(opponent, "statistics", default=[]):
        if "shotsOnTarget" in await async_get_value(statistic, "name", default=[]):
            new_values["opponent_shots_on_target"] = await async_get_value(
                statistic, "displayValue"
            )
        if "totalShots" in await async_get_value(statistic, "name", default=[]):
            new_values["opponent_total_shots"] = await async_get_value(
                statistic, "displayValue"
            )
        if "possessionPct" in await async_get_value(statistic, "name", default=[]):
            oppoPP = await async_get_value(statistic, "displayValue")

    #    _LOGGER.debug("%s: async_set_soccer_values() 3: %s", sensor_name, sensor_name)

    new_values["last_play"] = ""
    if teamPP and oppoPP:
        new_values["last_play"] = (
            new_values["team_abbr"]
            + " "
            + str(teamPP)
            + "%, "
            + new_values["opponent_abbr"]
            + " "
            + str(oppoPP)
            + "%; "
        )
    for detail in await async_get_value(
        event, "competitions", 0, "details", default=[]
    ):
        try:
            mls_team_id = await async_get_value(detail, "team", "id", default=0)

            new_values["last_play"] = (
                new_values["last_play"]
                + "     "
                + await async_get_value(
                    detail, "clock", "displayValue", default="{clock}"
                )
            )
            new_values["last_play"] = (
                new_values["last_play"]
                + "  "
                + await async_get_value(detail, "type", "text", default="{type}")
            )
            new_values["last_play"] = (
                new_values["last_play"]
                + ": "
                + await async_get_value(
                    detail,
                    "athletesInvolved",
                    0,
                    "displayName",
                    default="{displayName}",
                )
            )
            if mls_team_id == new_values["team_id"]:
                new_values["last_play"] = (
                    new_values["last_play"] + " (" + new_values["team_abbr"] + ")"
                )
            else:
                new_values["last_play"] = (
                    new_values["last_play"]
                    + " ("
                    + new_values["opponent_abbr"]
                    + ")          "
                )
        except:
            new_values["last_play"] = new_values["last_play"] + " {last_play} "

    return True
