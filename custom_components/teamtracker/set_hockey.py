async def async_get_in_hockey_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}

    new_values["clock"] = event["status"]["type"]["shortDetail"] # Period clock

    new_values["team_shots_on_target"] = 0
    for statistic in event["competitions"] [0] ["competitors"] [oppo_index] ["statistics"]:
        if "saves" in statistic["name"]:
            shots = int(old_values["team_score"]) + int(statistic["displayValue"])
            new_values["team_shots_on_target"] = str(shots)

    new_values["opponent_shots_on_target"] = 0
    for statistic in event["competitions"] [0] ["competitors"] [team_index] ["statistics"]:
        if "saves" in statistic["name"]:
            shots = int(old_values["opponent_score"]) + int(statistic["displayValue"])
            new_values["opponent_shots_on_target"] = str(shots)
            
    return new_values