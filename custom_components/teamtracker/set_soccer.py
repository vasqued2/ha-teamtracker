async def async_get_in_soccer_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}
    teamPP = None
    oppoPP = None

    new_values["team_shots_on_target"] = 0
    new_values["team_total_shots"] = 0
    for statistic in event["competitions"] [0] ["competitors"] [team_index] ["statistics"]:
        if "shotsOnTarget" in statistic["name"]:
            new_values["team_shots_on_target"] = statistic["displayValue"]
        if "totalShots" in statistic["name"]:
            new_values["team_total_shots"] = statistic["displayValue"]
        if "possessionPct" in statistic["name"]:
            teamPP = statistic["displayValue"]

    new_values["opponent_shots_on_target"] = 0
    new_values["opponent_total_shots"] = 0
    for statistic in event["competitions"] [0] ["competitors"] [oppo_index] ["statistics"]:
        if "shotsOnTarget" in statistic["name"]:
            new_values["opponent_shots_on_target"] = statistic["displayValue"]
        if "totalShots" in statistic["name"]:
            new_values["opponent_total_shots"] = statistic["displayValue"]
        if "possessionPct" in statistic["name"]:
            oppoPP = statistic["displayValue"]

    new_values["last_play"] = ''
    if teamPP and oppoPP:
        new_values["last_play"] = old_values["team_abbr"] + " " + str(teamPP) + "%, " + old_values["opponent_abbr"] + " " + str(oppoPP) + "%; "
    for detail in event["competitions"][0]["details"]:
        try:
            mls_team_id = detail["team"]["id"]
                            
            new_values["last_play"] = new_values["last_play"] + "     " + detail["clock"]["displayValue"]
            new_values["last_play"] = new_values["last_play"] + "  " + detail["type"]["text"]
            new_values["last_play"] = new_values["last_play"] + ": " + detail["athletesInvolved"][0]["displayName"]
            if mls_team_id == old_values["team_id"]:
                new_values["last_play"] = new_values["last_play"] + " (" + old_values["team_abbr"] + ")"
            else:
                new_values["last_play"] = new_values["last_play"] + " (" + old_values["opponent_abbr"] + ")          "
        except:
            new_values["last_play"] = new_values["last_play"] + " (Last play not found) "
    return new_values