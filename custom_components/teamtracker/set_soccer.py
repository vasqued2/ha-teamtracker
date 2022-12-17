import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_get_in_soccer_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}
    teamPP = None
    oppoPP = None

    new_values["team_shots_on_target"] = 0
    new_values["team_total_shots"] = 0
    for statistic in await async_get_value(event, "competitions", 0, "competitors", team_index, "statistics", default=[]):
        if "shotsOnTarget" in await async_get_value(statistic, "name", default=[]):
            new_values["team_shots_on_target"] = await async_get_value(statistic, "displayValue")
        if "totalShots" in await async_get_value(statistic, "name", default=[]):
            new_values["team_total_shots"] = await async_get_value(statistic, "displayValue")
        if "possessionPct" in await async_get_value(statistic, "name", default=[]):
            teamPP = await async_get_value(statistic, "displayValue")

    new_values["opponent_shots_on_target"] = 0
    new_values["opponent_total_shots"] = 0
    for statistic in await async_get_value(event, "competitions", 0, "competitors", oppo_index, "statistics", default=[]):
        if "shotsOnTarget" in await async_get_value(statistic, "name", default=[]):
            new_values["opponent_shots_on_target"] = await async_get_value(statistic, "displayValue")
        if "totalShots" in await async_get_value(statistic, "name", default=[]):
            new_values["opponent_total_shots"] = await async_get_value(statistic, "displayValue")
        if "possessionPct" in await async_get_value(statistic, "name", default=[]):
            oppoPP = await async_get_value(statistic, "displayValue")

    new_values["last_play"] = ''
    if teamPP and oppoPP:
        new_values["last_play"] = old_values["team_abbr"] + " " + str(teamPP) + "%, " + old_values["opponent_abbr"] + " " + str(oppoPP) + "%; "
    for detail in await async_get_value(event, "competitions", 0, "details", default=[]):
        try:
            mls_team_id = await async_get_value(detail, "team", "id", default=0)
                            
            new_values["last_play"] = new_values["last_play"] + "     " + await async_get_value(detail, "clock", "displayValue", default="0:00")
            new_values["last_play"] = new_values["last_play"] + "  " + await async_get_value(detail, "type", "text", default="")
            new_values["last_play"] = new_values["last_play"] + ": " + await async_get_value(detail, "athletesInvolved", 0, "displayName", default="")
            if mls_team_id == old_values["team_id"]:
                new_values["last_play"] = new_values["last_play"] + " (" + old_values["team_abbr"] + ")"
            else:
                new_values["last_play"] = new_values["last_play"] + " (" + old_values["opponent_abbr"] + ")          "
        except:
            new_values["last_play"] = new_values["last_play"] + " (Last play not found) "
    return new_values