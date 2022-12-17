from .utils import (
    async_get_value,
)

async def async_get_in_volleyball_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}

    new_values["clock"] = await async_get_value(event, "status", "type", "detail") # Set
    new_values["team_sets_won"] = old_values["team_score"]
    new_values["opponent_sets_won"] = old_values["opponent_score"]
    new_values["team_score"] = await async_get_value(event, "competitions", 0, "competitors", team_index, "linescores", -1, "value", 
                                        default=0)
    new_values["opponent_score"] = await async_get_value(event, "competitions", 0, "competitors", oppo_index, "linescores", -1, "value",
                                        default=0)

    new_values["last_play"] = ''
    sets = len(await async_get_value(event, "competitions", 0, "competitors", team_index, "linescores",
                        default=""))

    for x in range (0, sets):
        new_values["last_play"] = new_values["last_play"] + " Set " + str(x + 1) + ": "
        new_values["last_play"] = new_values["last_play"] + old_values["team_abbr"] + " "
        new_values["last_play"] = new_values["last_play"] + str(int(await async_get_value(event, "competitions", 0, "competitors", team_index, "linescores", x, "value",
                                                                                default=0))) + " "
        new_values["last_play"] = new_values["last_play"] + old_values["opponent_abbr"] + " "
        new_values["last_play"] = new_values["last_play"] + str(int(await async_get_value(event, "competitions", 0, "competitors", oppo_index, "linescores", x, "value",
                                                                                default=0))) + "; "
    return new_values