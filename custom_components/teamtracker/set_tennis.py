""" Tennis specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import get_value

_LOGGER = logging.getLogger(__name__)

class SetTennisMixin:
    _values: TeamTrackerValues

    def _set_tennis_values(
        self,
        event, grouping_index, competition_index, team_index
    ) -> bool:
        """Set tennis specific values"""

        #     _LOGGER.debug("%s: async_set_tennis_values() 0: %s %s %s", self._sensor_name, self._sensor_name, grouping_index, competition_index)

        oppo_index = 1 - team_index
            
        grouping = get_value(event, "groupings", grouping_index)
        if grouping is None:
            competition = get_value(event, "competitions", competition_index)
        else:
            competition = get_value(grouping, "competitions", competition_index)
        
        competitor = get_value(competition, "competitors", team_index)
        opponent = get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            #         _LOGGER.debug("%s: async_set_tennis_values() 0.1: %s", self._sensor_name, self._sensor_name)
            return False

        self._values.location = get_value(competition, "venue", "court")
        self._values.down_distance_text = get_value(competition, "round", "displayName")
        self._values.overunder = get_value(competition, "type", "text")
        self._values.team_rank = get_value(competitor, "tournamentSeed")
        self._values.opponent_rank = get_value(opponent, "tournamentSeed")

        self._values.clock = get_value(
            competition,
            "status",
            "type",
            "detail",
            default=get_value(event, "status", "type", "shortDetail"),
        )

        #     _LOGGER.debug("%s: async_set_tennis_values() 2: %s", self._sensor_name, self._sensor_name)

        # Current set score
        self._values.team_score = get_value(competitor, "linescores", -1, "value")
        self._values.opponent_score = get_value(opponent, "linescores", -1, "value")
        
        # Tiebreak points
        self._values.team_shots_on_target = get_value(competitor, "linescores", -1, "tiebreak")
        self._values.opponent_shots_on_target = get_value(opponent, "linescores", -1, "tiebreak")

        # Final Match Score (Sets Won)
        if self._values.state == "POST":
            t_sets = 0
            o_sets = 0
            for x in range(0, len(get_value(competitor, "linescores", default=[]))):
                if int(get_value(competitor, "linescores", x, "value", default=0)) > \
                    int(get_value(opponent, "linescores", x, "value", default=0)):
                    t_sets += 1
                else:
                    o_sets += 1
            self._values.team_score = str(t_sets)
            self._values.opponent_score = str(o_sets)

        # Construct last_play string for set history
        last_play = ""
        linescores = get_value(competitor, "linescores", default=[])
        sets_count = len(linescores)

        for x in range(0, sets_count):
            t_name = get_value(competitor, "athlete", "shortName", 
                        default=get_value(competitor, "roster", "shortDisplayName", default="{shortName}"))
            o_name = get_value(opponent, "athlete", "shortName",
                        default=get_value(opponent, "roster", "shortDisplayName", default="{shortName}"))
            
            t_val = int(get_value(competitor, "linescores", x, "value", default=0))
            o_val = int(get_value(opponent, "linescores", x, "value", default=0))
            
            last_play += f" Set {x + 1}: {t_name} {t_val} {o_name} {o_val}; "

        self._values.last_play = last_play

        # Sets won tracking (excluding current set if still live)
        team_sets_won = 0
        opponent_sets_won = 0
        for x in range(0, sets_count - 1):
            if get_value(competitor, "linescores", x, "value", default=0) > \
                get_value(opponent, "linescores", x, "value", default=0):
                team_sets_won += 1
            else:
                opponent_sets_won += 1
        self._values.team_sets_won = str(team_sets_won)
        self._values.opponent_sets_won = str(opponent_sets_won)

        return True