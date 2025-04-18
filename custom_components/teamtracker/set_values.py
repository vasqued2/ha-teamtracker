""" Set non-sport specific values """

import codecs
import logging

import arrow

from .const import DEFAULT_LOGO, DEFAULT_PROB, DEFAULT_REFRESH_RATE, RAPID_REFRESH_RATE
from .set_baseball import async_set_baseball_values
from .set_cricket import async_set_cricket_values
from .set_golf import async_set_golf_values
from .set_hockey import async_set_hockey_values
from .set_mma import async_set_mma_values
from .set_racing import async_set_racing_values
from .set_soccer import async_set_soccer_values
from .set_tennis import async_set_tennis_values
from .set_volleyball import async_set_volleyball_values
from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)
team_prob = {}
oppo_prob = {}


#
#  Set Values
#
async def async_set_values(
    new_values, event, grouping_index, competition_index, team_index, lang, sensor_name
) -> bool:
    """Function to set all new_values for the specified event/competition/team"""

    #    _LOGGER.debug("%s: async_set_values() 1: %s", sensor_name, sensor_name)

    oppo_index = 1 if team_index == 0 else 0
    grouping = await async_get_value(event, "groupings", grouping_index)
    if grouping is None:
        competition = await async_get_value(event, "competitions", competition_index)
    else:
        competition = await async_get_value(grouping, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        _LOGGER.debug(
            "%s: async_set_values() Invalid competition, competitor, or opponent: %s",
            sensor_name,
            sensor_name,
        )
        return False

    rc = await async_set_universal_values(
        new_values, event, grouping_index, competition_index, team_index, lang, sensor_name
    )
    if not rc:
        _LOGGER.debug(
            "%s: async_set_values() Bad rc from async_set_universal_values(): %s",
            sensor_name,
            sensor_name,
        )
        return False

    #
    #  Additional values only needed for team sports
    #
    if await async_get_value(competitor, "type") == "team":
        rc = await async_set_team_values(
            new_values, event, grouping_index, competition_index, team_index, lang, sensor_name
        )
        if not rc:
            _LOGGER.debug(
                "%s: async_set_values() Bad rc from async_set_team_values(): %s",
                sensor_name,
                sensor_name,
            )
            return False

    #    _LOGGER.debug("%s: async_set_values() 3: %s", sensor_name, new_values)

    if new_values["state"] == "PRE":
        rc = await async_set_pre_values(new_values, event)
        if not rc:
            _LOGGER.debug(
                "%s: async_set_values() Bad rc from async_set_pre_values(): %s",
                sensor_name,
                sensor_name,
            )
            return False

    if new_values["state"] == "IN":
        rc = await async_set_in_values(
            new_values, event, grouping_index, competition_index, team_index, sensor_name
        )
        if not rc:
            _LOGGER.debug(
                "%s: async_set_values() Bad rc from async_set_in_values(): %s",
                sensor_name,
                sensor_name,
            )
            return False
        #        _LOGGER.debug("%s: async_set_values() 3.1: %s", sensor_name, new_values)
        #
        #   Sport Specific Values
        #
        if new_values["sport"] == "baseball":
            rc = await async_set_baseball_values(
                new_values, event, competition_index, team_index, sensor_name
            )
        elif new_values["sport"] == "soccer":
            rc = await async_set_soccer_values(
                new_values, event, competition_index, team_index, sensor_name
            )
        elif new_values["sport"] == "volleyball":
            rc = await async_set_volleyball_values(
                new_values, event, competition_index, team_index, sensor_name
            )
        elif new_values["sport"] == "hockey":
            rc = await async_set_hockey_values(
                new_values, event, competition_index, team_index, sensor_name
            )
    if new_values["sport"] == "golf":
        rc = await async_set_golf_values(
            new_values, event, competition_index, team_index, lang, sensor_name
        )
    elif new_values["sport"] == "tennis":
        rc = await async_set_tennis_values(
            new_values, event, grouping_index, competition_index, team_index, lang, sensor_name
        )
    elif new_values["sport"] == "mma":
        rc = await async_set_mma_values(
            new_values, event, competition_index, team_index, lang, sensor_name
        )
    elif new_values["sport"] == "racing":
        rc = await async_set_racing_values(
            new_values, event, competition_index, team_index, lang, sensor_name
        )
    elif new_values["sport"] == "cricket":
        rc = await async_set_cricket_values(
            new_values, event, competition_index, team_index, lang, sensor_name
        )
    #    _LOGGER.debug("%s: async_set_values() 4: %s", sensor_name, sensor_name)
    if not rc:
        _LOGGER.debug(
            "%s: async_set_values() Bad rc from async_set_SPORT_values(): %s",
            sensor_name,
            sensor_name,
        )
        return False

    new_values["private_fast_refresh"] = False
    if new_values["state"] == "IN":
        new_values["private_fast_refresh"] = True
    if new_values["state"] == "PRE" and (
        abs((arrow.get(new_values["date"]) - arrow.now()).total_seconds()) < 
        (int(DEFAULT_REFRESH_RATE.total_seconds())*2)
    ):
        _LOGGER.debug(
            "%s: Event is within %s minutes, setting refresh rate to %s seconds.",
            sensor_name,
            int(DEFAULT_REFRESH_RATE.total_seconds()/60)*2,
            int(RAPID_REFRESH_RATE.total_seconds())
        )
        new_values["private_fast_refresh"] = True

    #    _LOGGER.debug("%s: async_set_values() 5: %s", sensor_name, new_values)

    return rc


#
#  Set Universal Values
#
async def async_set_universal_values(
    new_values, event, grouping_index, competition_index, team_index, lang, sensor_name
) -> bool:
    """Function to set new_values common for all sports"""

    #    _LOGGER.debug("%s: async_set_universal_values() 1: %s", sensor_name, sensor_name)

    oppo_index = 1 if team_index == 0 else 0
    grouping = await async_get_value(event, "groupings", grouping_index)
    if grouping is None:
        competition = await async_get_value(event, "competitions", competition_index)
    else:
        competition = await async_get_value(grouping, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        _LOGGER.debug(
            "%s: async_set_universal_values() 1.1: %s", sensor_name, sensor_name
        )
        return False

    new_values["state"] = str(
        await async_get_value(
            competition,
            "status",
            "type",
            "state",
            default=await async_get_value(event, "status", "type", "state"),
        )
    ).upper()
    new_values["season"] = await async_get_value(event, "season", "slug")

    new_values["event_name"] = await async_get_value(event, "shortName")
    new_values["event_url"] = await async_get_value(event, "links", 0, "href")
    new_values["date"] = await async_get_value(
        competition, "date", default=(await async_get_value(event, "date"))
    )

    #    _LOGGER.debug("%s: async_set_universal_values() 2: %s", sensor_name, sensor_name)

    try:
        new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize(locale=lang)
    except:
        try:
            new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize(
                locale=lang[:2]
            )
        except:
            new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize()

    new_values["series_summary"] = await async_get_value(
        competition,
        "series",
        "summary",
    )

    new_values["venue"] = await async_get_value(
        competition,
        "venue",
        "fullName",
        default=await async_get_value(event, "circuit", "fullName"),
    )

    state = await async_get_value(competition, "venue", "address", "state")
    country = await async_get_value(competition, "venue", "address", "country")

    new_values["location"] = await async_get_value(
        competition, "venue", "address", "city"
    )
    if state:
        if new_values["location"]:
            new_values["location"] = f'{new_values["location"]}, {state}'
        else:
            new_values["location"] = state
    if country:
        if new_values["location"]:
            new_values["location"] = f'{new_values["location"]}, {country}'
        else:
            new_values["location"] = country
    if new_values["location"] is None:
        new_values["location"] = await async_get_value(
            competition, "venue", "address", "summary"
        )

    #    _LOGGER.debug("%s: async_set_universal_values() 3: %s", sensor_name, sensor_name)

    new_values["tv_network"] = await async_get_value(
        competition, "broadcasts", 0, "names", 0
    )

    new_values["team_id"] = await async_get_value(competitor, "id")
    new_values["opponent_id"] = await async_get_value(opponent, "id")
    #    _LOGGER.debug("%s: async_set_universal_values() 4: %s", sensor_name, sensor_name)

    new_values["team_name"] = await async_get_value(
        competitor,
        "team",
        "shortDisplayName",
        default=await async_get_value(competitor, "athlete", "displayName",
            default=await async_get_value(competitor, "roster", "shortDisplayName")
        ),
    )
    new_values["team_long_name"] = await async_get_value(
        competitor,
        "team",
        "displayName",
        default=await async_get_value(competitor, "athlete", "displayName",
            default=await async_get_value(competitor, "roster", "displayName")
        ),
    )
    new_values["team_conference_id"] = await async_get_value(
        competitor,
        "team",
        "conferenceId"
    )
    new_values["opponent_name"] = await async_get_value(
        opponent,
        "team",
        "shortDisplayName",
        default=await async_get_value(opponent, "athlete", "displayName",
            default=await async_get_value(opponent, "roster", "shortDisplayName"),
        ),
    )
    new_values["opponent_long_name"] = await async_get_value(
        opponent,
        "team",
        "displayName",
        default=await async_get_value(opponent, "athlete", "displayName",
            default=await async_get_value(opponent, "roster", "displayName")
        ),
    )
    new_values["opponent_conference_id"] = await async_get_value(
        opponent,
        "team",
        "conferenceId"
    )
    new_values["team_record"] = await async_get_value(
        competitor, "records", 0, "summary"
    )
    new_values["opponent_record"] = await async_get_value(
        opponent, "records", 0, "summary"
    )

    new_values["team_logo"] = await async_get_value(
        competitor,
        "team",
        "logo",
        default=await async_get_value(
            competitor, "athlete", "flag", "href", default=DEFAULT_LOGO
        ),
    )
    new_values["opponent_logo"] = await async_get_value(
        opponent,
        "team",
        "logo",
        default=await async_get_value(
            opponent, "athlete", "flag", "href", default=DEFAULT_LOGO
        ),
    )
    new_values["team_url"] = await async_get_value(
        competitor,
        "team",
        "links",
        0,
        "href",
        )
    new_values["opponent_url"] = await async_get_value(
        opponent,
        "team",
        "links",
        0,
        "href",
        )
    #    _LOGGER.debug("%s: async_set_universal_values() 4: %s", sensor_name, sensor_name)

    new_values["quarter"] = await async_get_value(
        competition,
        "status",
        "period",
        default=await async_get_value(event, "status", "period"),
    )
    new_values["clock"] = await async_get_value(
        competition,
        "status",
        "type",
        "shortDetail",
        default=await async_get_value(event, "status", "type", "shortDetail"),
    )
    try:
        new_values["team_score"] = (
            str(await async_get_value(competitor, "score"))
            + "("
            + str(event["competitions"][0]["competitors"][team_index]["shootoutScore"])
            + ")"
        )
    except:
        new_values["team_score"] = await async_get_value(competitor, "score")
    try:
        new_values["opponent_score"] = (
            str(await async_get_value(opponent, "score"))
            + "("
            + str(event["competitions"][0]["competitors"][oppo_index]["shootoutScore"])
            + ")"
        )
    except:
        new_values["opponent_score"] = await async_get_value(opponent, "score")

    # Some APIs return boolean values as strings, so we need to convert them

    new_values["team_winner"] = await async_get_value(competitor, "winner")
    if new_values["team_winner"] == "true":
        new_values["team_winner"] = True;
    elif new_values["team_winner"] == "false":
        new_values["team_winner"] = False;

    new_values["opponent_winner"] = await async_get_value(opponent, "winner")
    if new_values["opponent_winner"] == "true":
        new_values["opponent_winner"] = True;
    elif new_values["opponent_winner"] == "false":
        new_values["opponent_winner"] = False;

    new_values["team_rank"] = await async_get_value(
        competitor, "curatedRank", "current"
    )
    if new_values["team_rank"] == 99:
        new_values["team_rank"] = None

    new_values["opponent_rank"] = await async_get_value(
        opponent, "curatedRank", "current"
    )
    if new_values["opponent_rank"] == 99:
        new_values["opponent_rank"] = None

    #    _LOGGER.debug("%s: async_set_universal_values() 5: %s", sensor_name, new_values)

    return True


#
#  Set Team Values
#
async def async_set_team_values(
    new_values, event, grouping_index, competition_index, team_index, lang, sensor_name
) -> bool:
    """Function to set new_values for team sports"""

    #    _LOGGER.debug("%s: async_set_team_values() 1: %s", sensor_name, sensor_name)

    oppo_index = 1 if team_index == 0 else 0
    grouping = await async_get_value(event, "groupings", grouping_index)
    if grouping is None:
        competition = await async_get_value(event, "competitions", competition_index)
    else:
        competition = await async_get_value(grouping, "competitions", competition_index)

    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        #        _LOGGER.debug("%s: async_set_team_values() 1.1: %s", sensor_name, sensor_name)
        return False

    #    _LOGGER.debug("%s: async_set_team_values() 2: %s", sensor_name, sensor_name)

    new_values["team_abbr"] = await async_get_value(competitor, "team", "abbreviation")
    new_values["opponent_abbr"] = await async_get_value(
        opponent, "team", "abbreviation"
    )

    #    _LOGGER.debug("%s: async_set_team_values() 3: %s", sensor_name, new_values)

    new_values["team_homeaway"] = await async_get_value(competitor, "homeAway")
    new_values["opponent_homeaway"] = await async_get_value(opponent, "homeAway")

    team_color = str(
        await async_get_value(competitor, "team", "color", default="D3D3D3")
    )
    oppo_color = str(await async_get_value(opponent, "team", "color", default="A9A9A9"))
    team_alt_color = str(
        await async_get_value(competitor, "team", "alternateColor", default=team_color)
    )
    oppo_alt_color = str(
        await async_get_value(opponent, "team", "alternateColor", default=oppo_color)
    )

    #    _LOGGER.debug("%s: async_set_team_values() 4: %s", sensor_name, team_color)

    new_values["team_colors"] = ["#" + team_color, "#" + team_alt_color]
    new_values["opponent_colors"] = ["#" + oppo_color, "#" + oppo_alt_color]

    #    _LOGGER.debug("%s: async_set_team_values() 4: %s", sensor_name, new_values)

    return True


#
#  PRE
#
async def async_set_pre_values(new_values, event) -> bool:
    """Function to set new_values common for PRE state"""

    new_values["odds"] = await async_get_value(
        event, "competitions", 0, "odds", 0, "details"
    )
    new_values["overunder"] = await async_get_value(
        event, "competitions", 0, "odds", 0, "overUnder"
    )

    return True


#
#  IN
#
async def async_set_in_values(
    new_values, event, grouping_index, competition_index, team_index, sensor_name
) -> dict:
    """Function to set new_values common for IN state"""

    #
    #  Pylint doesn't recognize values set by setdefault() method
    #
    global team_prob  # pylint: disable=global-variable-not-assigned
    global oppo_prob  # pylint: disable=global-variable-not-assigned

    #    _LOGGER.debug("%s: async_set_in_values() 1: %s", sensor_name, sensor_name)

    oppo_index = 1 if team_index == 0 else 0

    grouping = await async_get_value(event, "groupings", grouping_index)
    if grouping is None:
        competition = await async_get_value(event, "competitions", competition_index)
    else:
        competition = await async_get_value(grouping, "competitions", competition_index)

    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition is None or competitor is None or opponent is None:
        #        _LOGGER.debug("%s: async_set_in_values() 1.1: %s", sensor_name, sensor_name)
        return False

    #    _LOGGER.debug("%s: async_set_in_values() 2: %s", sensor_name, new_values)

    prob_key = (
        str(new_values["league"])
        + "-"
        + str(new_values["team_abbr"])
        + str(new_values["opponent_abbr"])
    )
    alt_lp = ", naq Zvpuvtna fgvyy fhpxf"
    new_values["down_distance_text"] = await async_get_value(
        competition, "situation", "downDistanceText"
    )
    new_values["possession"] = await async_get_value(
        competition, "situation", "possession"
    )

    if str(await async_get_value(competitor, "homeAway")) == "home":
        new_values["team_timeouts"] = await async_get_value(
            competition, "situation", "homeTimeouts"
        )
        new_values["opponent_timeouts"] = await async_get_value(
            competition, "situation", "awayTimeouts"
        )
        new_values["team_win_probability"] = await async_get_value(
            competition,
            "situation",
            "lastPlay",
            "probability",
            "homeWinPercentage",
            default=team_prob.setdefault(prob_key, DEFAULT_PROB),
        )
        new_values["opponent_win_probability"] = await async_get_value(
            competition,
            "situation",
            "lastPlay",
            "probability",
            "awayWinPercentage",
            default=oppo_prob.setdefault(prob_key, DEFAULT_PROB),
        )
    else:
        new_values["team_timeouts"] = await async_get_value(
            competition, "situation", "awayTimeouts"
        )
        new_values["opponent_timeouts"] = await async_get_value(
            competition, "situation", "homeTimeouts"
        )
        new_values["team_win_probability"] = await async_get_value(
            competition,
            "situation",
            "lastPlay",
            "probability",
            "awayWinPercentage",
            default=team_prob.setdefault(prob_key, DEFAULT_PROB),
        )
        new_values["opponent_win_probability"] = await async_get_value(
            competition,
            "situation",
            "lastPlay",
            "probability",
            "homeWinPercentage",
            default=oppo_prob.setdefault(prob_key, DEFAULT_PROB),
        )

    #    _LOGGER.debug("%s: async_set_in_values() 4: %s", sensor_name, sensor_name)

    team_prob.update({prob_key: new_values["team_win_probability"]})
    oppo_prob.update({prob_key: new_values["opponent_win_probability"]})
    new_values["last_play"] = await async_get_value(
        competition, "situation", "lastPlay", "text"
    )

    #    _LOGGER.debug("%s: async_set_in_values() 5: %s", sensor_name, sensor_name)

    if (
        (str(str(new_values["last_play"]).upper()).startswith("END "))
        and (str(codecs.decode(prob_key, "rot13")).endswith("ZVPUBFH"))
        and (oppo_prob.get(prob_key) > 0.6)
    ):
        new_values["last_play"] = new_values["last_play"] + codecs.decode(
            alt_lp, "rot13"
        )

    #    _LOGGER.debug("%s: async_set_in_values() 6: %s", sensor_name, sensor_name)

    return True
