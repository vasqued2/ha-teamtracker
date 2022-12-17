import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)

async def async_set_tennis_values(old_values, event, competition, competitor, lang, index, comp_index, sensor_name) -> dict:
        new_values = {}

#        _LOGGER.debug("%s: async_set_tennis_values() 100: %s", sensor_name, type(competition))

        if index == 0:
            oppo_index = 1
        else:
            oppo_index = 0

        new_values["state"] = await async_get_value(competition, "status", "type", "state")
#        _LOGGER.debug("%s: async_set_tennis_values() 0.1: %s", sensor_name, new_values)

        if new_values["state"] == None:
            new_values["state"] = await async_get_value(event, "status", "type", "state")
        new_values["state"] = new_values["state"].upper()

#        _LOGGER.debug("%s: async_set_tennis_values() 1: %s", sensor_name, new_values)


        team_index = index

        try:
            remaining_games = len(await async_get_value(event, "competitions", default="")) - comp_index;
#            _LOGGER.debug("%s: async_set_tennis_values() 4.1: %s %s %s", sensor_name, remaining_games, len(event["competitions"]), comp_index)

            new_values["odds"] = 1<<remaining_games.bit_length() # Game is in the round of X
        except:
            new_values["odds"] = None

        new_values["team_rank"] = await async_get_value(competitor, "tournamentSeed")
        new_values["opponent_rank"] = await async_get_value(competition, "competitors", oppo_index, "tournamentSeed")

        new_values["clock"] = await async_get_value(competition, "status", "type", "detail")
        if new_values["clock"] == None:
            new_values["clock"] = await async_get_value(event, "status", "type", "detail")

#        _LOGGER.debug("%s: async_set_tennis_values() 5: %s", sensor_name, sensor_name)

#        new_values["team_sets_won"] = new_values["team_score"]
#        new_values["opponent_sets_won"] = new_values["opponent_score"]

        new_values["team_score"] = await async_get_value(competitor, "score")
        new_values["opponent_score"] = await async_get_value(competition, "competitors", oppo_index, "score")

        new_values["team_score"] = await async_get_value(competitor, "linescores", -1, "value")
        new_values["opponent_score"] = await async_get_value(competition, "competitors", oppo_index, "linescores", -1, "value")
        new_values["team_shots_on_target"] = await async_get_value(competitor, "linescores", -1, "tiebreak")
        new_values["opponent_shots_on_target"] = await async_get_value(competition, "competitors", oppo_index, "linescores", -1, "tiebreak")

#        _LOGGER.debug("%s: async_set_tennis_values() 6: %s", sensor_name, sensor_name)

        if new_values["state"] == "POST":
            new_values["team_score"] = 0
            new_values["opponent_score"] = 0
#            _LOGGER.debug("%s: async_set_tennis_values() 7: %s", sensor_name, sensor_name)

            for x in range (0, len(await async_get_value(competitor, "linescores", default=[]))):
                if (int(await async_get_value(competitor, "linescores", x, "value", default=0)) > int(await async_get_value(competition, "competitors", oppo_index, "linescores", x, "value", default=0))):
                    new_values["team_score"] = new_values["team_score"] + 1
                else:
                    new_values["opponent_score"] = new_values["opponent_score"] + 1

        new_values["last_play"] = ''
        sets = len(await async_get_value(competitor, "linescores", default=[]))

#        _LOGGER.debug("%s: async_set_tennis_values() 8: %s", sensor_name, sensor_name)

        for x in range (0, sets):
            new_values["last_play"] = new_values["last_play"] + " Set " + str(x + 1) + ": "
            new_values["last_play"] = new_values["last_play"] + competitor["athlete"]["shortName"] + " "
            try:
                new_values["last_play"] = new_values["last_play"] + str(int(competitor["linescores"] [x] ["value"])) + " "
            except:
                new_values["last_play"] = new_values["last_play"] + "?? "
            new_values["last_play"] = new_values["last_play"] + competition["competitors"][oppo_index]["athlete"]["shortName"] + " "
            try:
                new_values["last_play"] = new_values["last_play"] + str(int(competition["competitors"][oppo_index] ["linescores"] [x] ["value"])) + "; "
            except:
                new_values["last_play"] = new_values["last_play"] + "??; "

        new_values["team_sets_won"] = 0
        new_values["opponent_sets_won"] = 0
        for x in range (0, sets - 1):
            try:
                if competitor["linescores"][x]["value"] > competition["competitors"][oppo_index]["linescores"][x]["value"]:
                    new_values["team_sets_won"] = new_values["team_sets_won"] + 1
                else:
                    new_values["opponent_sets_won"] = new_values["opponent_sets_won"] + 1
            except:
                new_values["team_sets_won"] = new_values["team_sets_won"]

#        _LOGGER.debug("%s: async_set_tennis_values() 9: %s", sensor_name, new_values)

        return(new_values)

