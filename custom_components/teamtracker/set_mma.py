""" MMA specific functionality"""

import logging

from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_set_mma_values(
    new_values, event, competition_index, team_index, lang, sensor_name
) -> bool:
    """Set MMA specific values"""

    _LOGGER.debug("%s: async_set_mma_values() 1: %s", sensor_name, sensor_name)

    oppo_index = 1 - team_index
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        #        _LOGGER.debug("%s: async_set_mma_values() 1.1: %s", sensor_name, sensor_name)
        return False

    #    _LOGGER.debug("%s: async_set_mma_values() 2: %s %s %s", sensor_name, competition_index, team_index, oppo_index)

    new_values["event_name"] = await async_get_value(event, "name")

    t = 0
    o = 0
    for ls in range(
        0,
        len(
            await async_get_value(
                competitor, "linescores", -1, "linescores", default=[]
            )
        ),
    ):
        #        _LOGGER.debug("%s: async_set_mma_values() 2.1: %s", sensor_name, ls)

        if await async_get_value(
            competitor, "linescores", -1, "linescores", ls, "value", default=0
        ) > await async_get_value(
            opponent, "linescores", -1, "linescores", ls, "value", default=0
        ):
            t = t + 1
        if await async_get_value(
            competitor, "linescores", -1, "linescores", ls, "value", default=0
        ) < await async_get_value(
            opponent, "linescores", -1, "linescores", ls, "value", default=0
        ):
            o = o + 1

        new_values["team_score"] = t
        new_values["opponent_score"] = o
    if t == o:
        #        _LOGGER.debug("%s: async_set_mma_values() 3: %s", sensor_name, sensor_name)
        if await async_get_value(competitor, "winner", default=False):
            new_values["team_score"] = "W"
            new_values["opponent_score"] = "L"
        if await async_get_value(opponent, "winner", default=False):
            new_values["team_score"] = "L"
            new_values["opponent_score"] = "W"

    #    _LOGGER.debug("%s: async_set_mma_values() 4: %s %s %s", sensor_name, competition_index, team_index, oppo_index)
    new_values["last_play"] = await async_get_prior_fights(event, sensor_name)

    #    _LOGGER.debug("%s: async_set_mma_values() 5: %s %s %s", sensor_name, competition_index, team_index, oppo_index)

    return True


async def async_get_prior_fights(event, sensor_name) -> str:
    """Get the results of the prior fights"""

    prior_fights = ""

    #    _LOGGER.debug("%s: async_get_prior_fights() 1: %s", sensor_name, sensor_name)
    c = 1
    for competition in await async_get_value(event, "competitions", default=[]):
        #        _LOGGER.debug("%s: async_get_prior_fights() 2: %s", sensor_name, sensor_name)

        if (
            str(
                await async_get_value(
                    competition, "status", "type", "state", default="NOT_FOUND"
                )
            ).upper()
            == "POST"
        ):
            #            _LOGGER.debug("%s: async_get_prior_fights() 2.1: %s", sensor_name, sensor_name)

            prior_fights = prior_fights + str(c) + ". "
            if await async_get_value(
                competition, "competitors", 0, "winner", default=False
            ):
                prior_fights = (
                    prior_fights
                    + "*"
                    + str(
                        await async_get_value(
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
                    await async_get_value(
                        competition,
                        "competitors",
                        0,
                        "athlete",
                        "shortName",
                        default="{shortName}",
                    )
                )
            prior_fights = prior_fights + " v. "
            if await async_get_value(
                competition, "competitors", 1, "winner", default=False
            ):
                prior_fights = (
                    prior_fights
                    + str(
                        await async_get_value(
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
                    await async_get_value(
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
            #            _LOGGER.debug("%s: async_get_prior_fights() 2.2: %s", sensor_name, len(await async_get_value(competition, "competitors", 0, "linescores", 0, "linescores", default=[])))
            for ls in range(
                0,
                len(
                    await async_get_value(
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
                    await async_get_value(
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
                    await async_get_value(
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
                    await async_get_value(
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
                    await async_get_value(
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
                        await async_get_value(
                            competition, "status", "period", default="{period}"
                        )
                    )
                    + "@"
                    + str(
                        await async_get_value(
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
