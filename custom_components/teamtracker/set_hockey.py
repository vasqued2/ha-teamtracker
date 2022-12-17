import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)

async def async_get_in_hockey_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}

    new_values["clock"] = await async_get_value(event, "status", "type", "shortDetail") # Period clock

    new_values["team_shots_on_target"] = 0
    for statistic in await async_get_value(event, "competitions", 0, "competitors", oppo_index, "statistics", 
                                default=[]):
        if "saves" in await async_get_value(statistic, "name", 
                                default=[]):
            shots = int(old_values["team_score"]) + int(await async_get_value(statistic, "displayValue", 
                                                                    default=0))
            new_values["team_shots_on_target"] = str(shots)

    new_values["opponent_shots_on_target"] = 0
    for statistic in await async_get_value(event, "competitions", 0, "competitors", team_index, "statistics", 
                                default=[]):
        if "saves" in await async_get_value(statistic, "name", 
                                default=[]):
            shots = int(old_values["opponent_score"]) + int(await async_get_value(statistic, "displayValue", 
                                                                        default=0))
            new_values["opponent_shots_on_target"] = str(shots)
            
    return new_values