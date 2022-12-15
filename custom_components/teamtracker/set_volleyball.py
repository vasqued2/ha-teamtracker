async def async_get_in_volleyball_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}


    new_values["clock"] = event["status"]["type"]["detail"] # Set
    new_values["team_sets_won"] = old_values["team_score"]
    new_values["opponent_sets_won"] = old_values["opponent_score"]
    try:
        new_values["team_score"] = event["competitions"] [0] ["competitors"] [team_index] ["linescores"] [-1] ["value"]
    except:
        new_values["team_score"] = 0
    try:
        new_values["opponent_score"] = event["competitions"] [0] ["competitors"] [oppo_index] ["linescores"] [-1] ["value"]
    except:
        new_values["opponent_score"] = 0
                            
    new_values["last_play"] = ''
    try:
        sets = len(event["competitions"] [0] ["competitors"] [team_index] ["linescores"])
    except:
        sets = 0
    for x in range (0, sets):
        new_values["last_play"] = new_values["last_play"] + " Set " + str(x + 1) + ": "
        new_values["last_play"] = new_values["last_play"] + old_values["team_abbr"] + " "
        try:
            new_values["last_play"] = new_values["last_play"] + str(int(event["competitions"] [0] ["competitors"] [team_index] ["linescores"] [x] ["value"])) + " "
        except:
            new_values["last_play"] = new_values["last_play"] + "?? "
        new_values["last_play"] = new_values["last_play"] + old_values["opponent_abbr"] + " "
        try:
            new_values["last_play"] = new_values["last_play"] + str(int(event["competitions"] [0] ["competitors"] [oppo_index] ["linescores"] [x] ["value"])) + "; "
        except:
            new_values["last_play"] = new_values["last_play"] + "??; "

    return new_values