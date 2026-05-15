""" Golf specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import async_get_value, is_integer

_LOGGER = logging.getLogger(__name__)

class SetGolfMixin:

    async def _async_set_golf_values(
        self,
        new_values, event, competition_index, team_index
    ) -> bool:
        """Set golf specific values"""

        self._values = TeamTrackerValues.from_dict(new_values)

        oppo_index = 1 if team_index == 0 else 0
        competition = await async_get_value(event, "competitions", competition_index)
        competitor = await async_get_value(competition, "competitors", team_index)
        opponent = await async_get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            return False

        if self._values.state in ["IN", "POST"]:
            self._values.team_rank = await self._async_get_golf_position(competition, team_index)
            self._values.opponent_rank = await self._async_get_golf_position(
                competition, oppo_index
            )
        else:
            self._values.team_rank = None
            self._values.opponent_rank = None

        if self._values.state in ["IN", "POST"]:
            if self._values.quarter and is_integer(self._values.quarter):
                golf_round = int(self._values.quarter) - 1
            else:
                golf_round = 0

            self._values.team_total_shots = await async_get_value(
                competitor, "linescores", golf_round, "value", default=0
            )
            self._values.team_shots_on_target = len(
                await async_get_value(
                    competitor, "linescores", golf_round, "linescores", default=[]
                )
            )
            self._values.opponent_total_shots = await async_get_value(
                opponent, "linescores", golf_round, "value", default=0
            )
            self._values.opponent_shots_on_target = len(
                await async_get_value(
                    opponent, "linescores", golf_round, "linescores", default=[]
                )
            )

            self._values.last_play = ""
            for x in range(0, 10):
                p = await self._async_get_golf_position(competition, x)
                self._values.last_play = self._values.last_play + p + ". "
                self._values.last_play = self._values.last_play + await async_get_value(
                    competition, "competitors", x, "athlete", "shortName", 
                    default=await async_get_value(
                        competition, "competitors", x, "team", "shortDisplayName", default=""
                    )
                )
                self._values.last_play = (
                    str(self._values.last_play)
                    + " ("
                    + str(
                        await async_get_value(
                            competition, "competitors", x, "score", default=""
                        )
                    )
                    + "),   "
                )

            self._values.last_play = self._values.last_play[:-1]

        new_values.update(self._values.to_dict())

        return True


    async def _async_get_golf_position(self, competition, index) -> str:
        """Determine the position of index considering ties if score matches leading or trailing position"""

        t = 0
        tie = ""
        for x in range(1, index + 1):
            if await async_get_value(
                competition, "competitors", x, "score", default=1000
            ) == await async_get_value(
                competition, "competitors", t, "score", default=1001
            ):
                tie = "T"
            else:
                tie = ""
                t = x
        if await async_get_value(
            competition, "competitors", index, "score", default=1000
        ) == await async_get_value(
            competition, "competitors", index + 1, "score", default=1001
        ):
            tie = "T"

        return tie + str(t + 1)