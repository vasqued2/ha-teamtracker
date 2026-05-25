""" MMA specific functionality"""

import logging

from .models import TeamTrackerValues
from .utils import get_value

_LOGGER = logging.getLogger(__name__)

class SetMMAMixin:
    _sensor_name: str
    _values: TeamTrackerValues

    def _set_mma_values(
        self,
        event, competition_index, team_index
    ) -> bool:
        """Set MMA specific values"""

        _LOGGER.debug("%s: async_set_mma_values() 1: %s", self._sensor_name, self._sensor_name)

        oppo_index = 1 - team_index
        competition = get_value(event, "competitions", competition_index)
        competitor = get_value(competition, "competitors", team_index)
        opponent = get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            #        _LOGGER.debug("%s: async_set_mma_values() 1.1: %s", sensor_name, sensor_name)
            return False

        #    _LOGGER.debug("%s: async_set_mma_values() 2: %s %s %s", sensor_name, competition_index, team_index, oppo_index)

        self._values.event_name = get_value(event, "name")

        t = 0
        o = 0
        for ls in range(
            0,
            len(
                get_value(
                    competitor, "linescores", -1, "linescores", default=[]
                )
            ),
        ):
            #        _LOGGER.debug("%s: async_set_mma_values() 2.1: %s", sensor_name, ls)

            if get_value(
                competitor, "linescores", -1, "linescores", ls, "value", default=0
            ) > get_value(
                opponent, "linescores", -1, "linescores", ls, "value", default=0
            ):
                t = t + 1
            if get_value(
                competitor, "linescores", -1, "linescores", ls, "value", default=0
            ) < get_value(
                opponent, "linescores", -1, "linescores", ls, "value", default=0
            ):
                o = o + 1

            self._values.team_score = str(t)
            self._values.opponent_score = str(o)
        if t == o:
            #        _LOGGER.debug("%s: async_set_mma_values() 3: %s", sensor_name, sensor_name)
            if get_value(competitor, "winner", default=False):
                self._values.team_score = "W"
                self._values.opponent_score = "L"
            if get_value(opponent, "winner", default=False):
                self._values.team_score = "L"
                self._values.opponent_score = "W"

        #    _LOGGER.debug("%s: async_set_mma_values() 4: %s %s %s", sensor_name, competition_index, team_index, oppo_index)
        self._values.last_play = self._get_prior_fights(event)

        #     _LOGGER.debug("%s: async_set_mma_values() 5: %s %s %s", sensor_name, competition_index, team_index, oppo_index)

        return True


    def _get_prior_fights(self, event) -> str:
        """Get the results of the prior fights"""

        prior_fights = ""

        #    _LOGGER.debug("%s: async_get_prior_fights() 1: %s", sensor_name, sensor_name)
        c = 1
        for competition in get_value(event, "competitions", default=[]):
            #        _LOGGER.debug("%s: _get_prior_fights() 2: %s", sensor_name, sensor_name)

            if (
                str(
                    get_value(
                        competition, "status", "type", "state", default="NOT_FOUND"
                    )
                ).upper()
                == "POST"
            ):
                #            _LOGGER.debug("%s: async_get_prior_fights() 2.1: %s", sensor_name, sensor_name)

                prior_fights = prior_fights + str(c) + ". "
                if get_value(
                    competition, "competitors", 0, "winner", default=False
                ):
                    prior_fights = (
                        prior_fights
                        + "*"
                        + str(
                            get_value(
                                competition,
                                "competitors",
                                0,
                                "athlete",
                                "shortName",
                                default="{shortName}",
                            )
                        ).upper()
                    )
                else:
                    prior_fights = prior_fights + str(
                        get_value(
                            competition,
                            "competitors",
                            0,
                            "athlete",
                            "shortName",
                            default="{shortName}",
                        )
                    )
                prior_fights = prior_fights + " v. "
                if get_value(
                    competition, "competitors", 1, "winner", default=False
                ):
                    prior_fights = (
                        prior_fights
                        + str(
                            get_value(
                                competition,
                                "competitors",
                                1,
                                "athlete",
                                "shortName",
                                default="{shortName}",
                            )
                        ).upper()
                        + "*"
                    )
                else:
                    prior_fights = prior_fights + str(
                        get_value(
                            competition,
                            "competitors",
                            1,
                            "athlete",
                            "shortName",
                            default="{shortName}",
                        )
                    )
                f1 = 0
                f2 = 0
                t = 0
                #            _LOGGER.debug("%s: async_get_prior_fights() 2.2: %s", sensor_name, len(get_value(competition, "competitors", 0, "linescores", 0, "linescores", default=[])))
                for ls in range(
                    0,
                    len(
                        get_value(
                            competition,
                            "competitors",
                            0,
                            "linescores",
                            0,
                            "linescores",
                            default=[],
                        )
                    ),
                ):
                    #                _LOGGER.debug("%s: async_get_prior_fights() 2.3: %s %s %s %s", sensor_name, ls, f1, f2, t)
                    if int(
                        get_value(
                            competition,
                            "competitors",
                            0,
                            "linescores",
                            0,
                            "linescores",
                            ls,
                            "value",
                            default=0,
                        )
                    ) > int(
                        get_value(
                            competition,
                            "competitors",
                            1,
                            "linescores",
                            0,
                            "linescores",
                            ls,
                            "value",
                            default=0,
                        )
                    ):
                        f1 = f1 + 1
                    elif int(
                        get_value(
                            competition,
                            "competitors",
                            0,
                            "linescores",
                            0,
                            "linescores",
                            ls,
                            "value",
                            default=0,
                        )
                    ) < int(
                        get_value(
                            competition,
                            "competitors",
                            1,
                            "linescores",
                            0,
                            "linescores",
                            ls,
                            "value",
                            default=0,
                        )
                    ):
                        f2 = f2 + 1
                    else:
                        t = t + 1

                #            _LOGGER.debug("%s: async_get_prior_fights() 3: %s %s %s %s %s", sensor_name, f1, f2, t, prior_fights)

                if f1 == 0 and f2 == 0 and t == 0:
                    prior_fights = (
                        prior_fights
                        + " (KO/TKO/Sub: R"
                        + str(
                            get_value(
                                competition, "status", "period", default="{period}"
                            )
                        )
                        + "@"
                        + str(
                            get_value(
                                competition,
                                "status",
                                "displayClock",
                                default="{displayClock}",
                            )
                        )
                    )
                else:
                    prior_fights = prior_fights + " (Dec: " + str(f1) + "-" + str(f2)
                    if t != 0:
                        prior_fights = prior_fights + "-" + str(t)

                prior_fights = prior_fights + "); "
                c = c + 1
        #            _LOGGER.debug("%s: async_get_prior_fights() 4: %s", sensor_name, prior_fights)

        return prior_fights