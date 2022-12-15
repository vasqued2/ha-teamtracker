async def async_get_in_baseball_event_attributes(event, old_values) -> dict:
    """Get IN event values"""
    new_values = {}


    new_values["clock"] = event["status"]["type"]["detail"] # Inning
    if new_values["clock"][:3].lower() in ['bot','mid']:
        if old_values["team_homeaway"] in ["home"]: # Home outs, at bat in bottom of inning
            new_values["possession"] = old_values["team_id"]
        else: # Away outs, at bat in bottom of inning
            new_values["possession"] = old_values["opponent_id"]
    else:
        if old_values["team_homeaway"] in ["away"]: # Away outs, at bat in top of inning
            new_values["possession"] = old_values["team_id"]
        else:  # Home outs, at bat in top of inning
            new_values["possession"] = old_values["opponent_id"]
    try:
        new_values["outs"] = event["competitions"][0]["situation"]["outs"]
    except:
        new_values["outs"] = None
    try: # Balls
        new_values["balls"] = event["competitions"][0]["situation"]["balls"]
    except:
        new_values["balls"] = None
    try: # Strikes
        new_values["strikes"] = event["competitions"][0]["situation"]["strikes"]
    except:
        new_values["strikes"] = None
    try: # Baserunners
        new_values["on_first"] = event["competitions"][0]["situation"]["onFirst"]
        new_values["on_second"] = event["competitions"][0]["situation"]["onSecond"]
        new_values["on_third"] = event["competitions"][0]["situation"]["onThird"]
    except:
        new_values["on_first"] = None
        new_values["on_second"] = None
        new_values["on_third"] = None

    return new_values