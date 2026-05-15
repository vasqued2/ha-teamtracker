""" Tennis specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)

class SetTennisMixin:

    async def _async_set_tennis_values(
        self,
        new_values, event, grouping_index, competition_index, team_index
    ) -> bool:
        """Set tennis specific values"""

        self._values = TeamTrackerValues.from_dict(new_values)

        #     _LOGGER.debug("%s: async_set_tennis_values() 0: %s %s %s", self._sensor_name, self._sensor_name, grouping_index, competition_index)

        oppo_index = 1 - team_index
            
        grouping = await async_get_value(event, "groupings", grouping_index)
        if grouping is None:
            competition = await async_get_value(event, "competitions", competition_index)
        else:
            competition = await async_get_value(grouping, "competitions", competition_index)
        
        competitor = await async_get_value(competition, "competitors", team_index)
        opponent = await async_get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            #         _LOGGER.debug("%s: async_set_tennis_values() 0.1: %s", self._sensor_name, self._sensor_name)
            return False

        self._values.location = await async_get_value(competition, "venue", "court")
        self._values.down_distance_text = await async_get_value(competition, "round", "displayName")
        self._values.overunder = await async_get_value(competition, "type", "text")
        self._values.team_rank = await async_get_value(competitor, "tournamentSeed")
        self._values.opponent_rank = await async_get_value(opponent, "tournamentSeed")

        self._values.clock = await async_get_value(
            competition,
            "status",
            "type",
            "detail",
            default=await async_get_value(event, "status", "type", "shortDetail"),
        )

        #     _LOGGER.debug("%s: async_set_tennis_values() 2: %s", self._sensor_name, self._sensor_name)

        # Current set score
        self._values.team_score = await async_get_value(competitor, "linescores", -1, "value")
        self._values.opponent_score = await async_get_value(opponent, "linescores", -1, "value")
        
        # Tiebreak points
        self._values.team_shots_on_target = await async_get_value(competitor, "linescores", -1, "tiebreak")
        self._values.opponent_shots_on_target = await async_get_value(opponent, "linescores", -1, "tiebreak")

        # Final Match Score (Sets Won)
        if self._values.state == "POST":
            t_sets = 0
            o_sets = 0
            for x in range(0, len(await async_get_value(competitor, "linescores", default=[]))):
                if int(await async_get_value(competitor, "linescores", x, "value", default=0)) > \
                    int(await async_get_value(opponent, "linescores", x, "value", default=0)):
                    t_sets += 1
                else:
                    o_sets += 1
            self._values.team_score = str(t_sets)
            self._values.opponent_score = str(o_sets)

        # Construct last_play string for set history
        last_play = ""
        linescores = await async_get_value(competitor, "linescores", default=[])
        sets_count = len(linescores)

        for x in range(0, sets_count):
            t_name = await async_get_value(competitor, "athlete", "shortName", 
                        default=await async_get_value(competitor, "roster", "shortDisplayName", default="{shortName}"))
            o_name = await async_get_value(opponent, "athlete", "shortName",
                        default=await async_get_value(opponent, "roster", "shortDisplayName", default="{shortName}"))
            
            t_val = int(await async_get_value(competitor, "linescores", x, "value", default=0))
            o_val = int(await async_get_value(opponent, "linescores", x, "value", default=0))
            
            last_play += f" Set {x + 1}: {t_name} {t_val} {o_name} {o_val}; "

        self._values.last_play = last_play

        # Sets won tracking (excluding current set if still live)
        team_sets_won = 0
        opponent_sets_won = 0
        for x in range(0, sets_count - 1):
            if await async_get_value(competitor, "linescores", x, "value", default=0) > \
                await async_get_value(opponent, "linescores", x, "value", default=0):
                team_sets_won += 1
            else:
                opponent_sets_won += 1
        self._values.team_sets_won = str(team_sets_won)
        self._values.opponent_sets_won = str(opponent_sets_won)

        new_values.update(self._values.to_dict())
        return True