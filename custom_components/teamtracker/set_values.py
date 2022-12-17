import arrow
import logging
import codecs

from .utils import async_get_value
from .set_golf import async_set_golf_values
from .set_mma import async_set_mma_values
from .set_racing import async_set_racing_values
from .set_tennis import async_set_tennis_values

from .const import (
    DEFAULT_LOGO,
    DEFAULT_PROB,
)

_LOGGER = logging.getLogger(__name__)
team_prob = {}
oppo_prob = {}

async def async_set_values(old_values, event, competition_index, team_index, lang, sensor_name) -> dict:
    new_values = {}

#    _LOGGER.debug("%s: async_set_values() 1: %s", sensor_name, sensor_name)

    if team_index == 0:
        oppo_index = 1
    else:
        oppo_index = 0
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition == None or competitor == None or opponent == None:
        return(new_values)


    new_values["key"] = "value"

    new_values["sport"] = old_values["sport"]
    new_values["league"] = old_values["league"]
    new_values["team_abbr"] = old_values["team_abbr"]
    new_values["opponent_abbr"] = None

#    _LOGGER.debug("%s: async_set_values() 1.1: %s", sensor_name, sensor_name)

#    _LOGGER.debug("%s: async_set_values() 1.1.1: %s", sensor_name, sensor_name)
    new_values["state"] = str(await async_get_value(competition, "status", "type", "state",
        default=await async_get_value(event, "status", "type", "state"))).upper()
#    _LOGGER.debug("%s: async_set_values() 1.1.2: %s", sensor_name, sensor_name)
    new_values["event_name"] = await async_get_value(event, "shortName")
#    _LOGGER.debug("%s: async_set_values() 1.1.3: %s", sensor_name, sensor_name)
    new_values["date"] = await async_get_value(competition, "date",
        default=(await async_get_value(event, "date")))

#    _LOGGER.debug("%s: async_set_values() 1.2: %s", sensor_name, sensor_name)

    try:
        new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize(locale=lang)
    except:
        try:
            new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize(locale=lang[:2])
        except:
            new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize()

    new_values["venue"] = await async_get_value(competition, "venue", "fullName")

#    _LOGGER.debug("%s: async_set_values() 1.3: %s", sensor_name, sensor_name)

    try:
        new_values["location"] = "%s, %s" % (competition["venue"]["address"]["city"], competition["venue"]["address"]["state"])
    except:
        new_values["location"] = await async_get_value(competition, "venue", "address", "city",
            default=await async_get_value(competition, "venue", "address", "summary"))

#    _LOGGER.debug("%s: async_set_values() 1.4: %s", sensor_name, sensor_name)

    new_values["tv_network"] = await async_get_value(competition, "broadcasts", 0, "names", 0)
    new_values["odds"] = await async_get_value(competition, "odds", 0, "details")
    new_values["overunder"] = await async_get_value(competition, "odds", 0, "overUnder")
    new_values["quarter"] = await async_get_value(competition, "status", "period")
    new_values["clock"] = await async_get_value(competition, "status", "type", "shortDetail",
        default=await async_get_value(event, "status", "type", "shortDetail"))

#    _LOGGER.debug("%s: async_set_values() 2: %s", sensor_name, sensor_name)

#    new_values["team_abbr"] = competitor["team"]["abbreviation"]
    new_values["team_id"] = await async_get_value(competitor, "id")
    new_values["opponent_id"] = await async_get_value(competition, "competitors", oppo_index, "id")

    new_values["team_name"] = await async_get_value(competitor, "athlete", "displayName")
    new_values["opponent_name"] = await async_get_value(competition, "competitors", oppo_index, "athlete", "displayName")
    new_values["team_record"] = await async_get_value(competitor, "records", 0, "summary")
    new_values["opponent_record"] = await async_get_value(competition, "competitors", oppo_index, "records", 0, "summary")
    new_values["team_logo"] = await async_get_value(competitor, "athlete", "flag", "href",
        default=DEFAULT_LOGO)
    new_values["opponent_logo"] = await async_get_value(competition, "competitors", oppo_index, "athlete", "flag", "href",
        default=DEFAULT_LOGO)
    new_values["team_score"] = await async_get_value(competitor, "score")
    new_values["opponent_score"] = await async_get_value(competition, "competitors", oppo_index, "score")

    new_values["team_rank"] = await async_get_value(competitor, "curatedRank", "current")
    if new_values["team_rank"] == 99:
        new_values["team_rank"] = None

    new_values["opponent_rank"] = await async_get_value(competition, "competitors", oppo_index, "curatedRank", "current")
    if new_values["opponent_rank"] == 99:
        new_values["opponent_rank"] = None

#    _LOGGER.debug("%s: async_set_values() 3: %s", sensor_name, sensor_name)

    if new_values["state"] == "IN":
        _LOGGER.debug("%s: Event in progress, setting refresh rate to 5 seconds.", sensor_name)
        new_values["private_fast_refresh"] = True
    if new_values["state"] == 'PRE' and (abs((arrow.get(new_values["date"])-arrow.now()).total_seconds()) < 1200):
        _LOGGER.debug("%s: Event is within 20 minutes, setting refresh rate to 5 seconds.", sensor_name)
        new_values["private_fast_refresh"] = True

#
#   Sport Specify Values
#
    if (new_values["sport"] == "golf"):
        new_values.update(await async_set_golf_values(old_values, event, competition, competitor, lang, team_index, competition_index, sensor_name))
    if (new_values["sport"] == "tennis"):
        new_values.update(await async_set_tennis_values(old_values, event, competition, competitor, lang, team_index, competition_index, sensor_name))
    if (new_values["sport"] == "mma"):
        new_values.update(await async_set_mma_values(old_values, event, competition, competitor, lang, team_index, competition_index, sensor_name))
    if (new_values["sport"] == "racing"):
        new_values.update(await async_set_racing_values(old_values, event, competition, competitor, lang, team_index, competition_index, sensor_name))

    return new_values



async def async_set_universal_values(new_values, event, competition_index, team_index, lang) -> bool:
    """Traverse JSON for universal values"""
#    new_values = {}
    if team_index == 0:
        oppo_index = 1
    else:
        oppo_index = 0
    competition = await async_get_value(event, "competitions", competition_index)
    competitor = await async_get_value(competition, "competitors", team_index)
    opponent = await async_get_value(competition, "competitors", oppo_index)

    if competition == None or competitor == None or opponent == None:
        return(False)

    new_values["state"] = str(await async_get_value(competition, "status", "type", "state",
        default=await async_get_value(event, "status", "type", "state"))).upper()
    new_values["event_name"] = await async_get_value(event, "shortName")
    new_values["date"] = await async_get_value(competition, "date",
        default=(await async_get_value(event, "date")))

    try:
        new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize(locale=lang)
    except:
        try:
            new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize(locale=lang[:2])
        except:
            new_values["kickoff_in"] = arrow.get(new_values["date"]).humanize()

    new_values["venue"] = await async_get_value(competition, "venue", "fullName")

    try:
        new_values["location"] = "%s, %s" % (competition["venue"]["address"]["city"], competition["venue"]["address"]["state"])
    except:
        new_values["location"] = await async_get_value(competition, "venue", "address", "city",
            default=await async_get_value(competition, "venue", "address", "summary"))


    new_values["tv_network"] = await async_get_value(competition, "broadcasts", 0, "names", 0)



    new_values["team_id"] = await async_get_value(competitor, "id")
    new_values["opponent_id"] = await async_get_value(opponent, "id")

    new_values["team_name"] = await async_get_value(competitor, "athlete", "displayName")
    new_values["opponent_name"] = await async_get_value(opponent, "athlete", "displayName")
    new_values["team_record"] = await async_get_value(competitor, "records", 0, "summary")
    new_values["opponent_record"] = await async_get_value(opponent, "records", 0, "summary")

    new_values["team_score"] = await async_get_value(competitor, "score")
    try:
        new_values["team_score"] = new_values["team_score"] + "(" + event["competitions"][0]["competitors"][team_index]["shootoutScore"] + ")"
    except:
        new_values["team_score"] = new_values["team_score"]
    new_values["opponent_score"] = await async_get_value(opponent, "score")
    try:
        new_values["opponent_score"] = new_values["opponent_score"] + "(" + event["competitions"][0]["competitors"][oppo_index]["shootoutScore"] + ")"
    except:
        new_values["opponent_score"] = new_values["opponent_score"]

    new_values["team_rank"] = await async_get_value(competitor, "curatedRank", "current")
    if new_values["team_rank"] == 99:
        new_values["team_rank"] = None

    new_values["opponent_rank"] = await async_get_value(opponent, "curatedRank", "current")
    if new_values["opponent_rank"] == 99:
        new_values["opponent_rank"] = None



#
#  Athlete specific values
#
#    new_values["team_logo"] = await async_get_value(competitor, "athlete", "flag", "href",
#        default=DEFAULT_LOGO)
#    new_values["opponent_logo"] = await async_get_value(opponent, "athlete", "flag", "href",
#        default=DEFAULT_LOGO)

#
#  Team Specific Values
#
    new_values["team_abbr"] = await async_get_value(competitor, "team", "abbreviation")
    new_values["team_logo"] = await async_get_value(competitor, "team", "logo", 
        default=DEFAULT_LOGO)
    new_values["opponent_abbr"] = await async_get_value(opponent, "team", "abbreviation")
    new_values["opponent_logo"] = await async_get_value(opponent, "team", "logo", 
        default=DEFAULT_LOGO)

    new_values["team_homeaway"] = event["competitions"][0]["competitors"][team_index]["homeAway"]
    try:
        color = '#' + event["competitions"][0]["competitors"][team_index]["team"]["color"]
    except:
        if new_values["team_id"] == 'NFC':
            color = '#013369'
        elif new_values["team_id"] == 'AFC':
            color = '#D50A0A'
        else:
            color = "#D3D3D3"
    try:
        alt_color = '#' + event["competitions"][0]["competitors"][team_index]["team"]["alternateColor"]
    except:
        alt_color = color
    new_values["team_colors"] = [color, alt_color]

    new_values["opponent_homeaway"] = event["competitions"][0]["competitors"][oppo_index]["homeAway"]
    try:
        color = '#' + event["competitions"][0]["competitors"][oppo_index]["team"]["color"]
    except:
        if new_values["team_id"] == 'NFC':
            color = '#013369'
        elif new_values["team_id"] == 'AFC':
            color = '#D50A0A'
        else:
            color = "#A9A9A9"
    try:
        alt_color = '#' + event["competitions"][0]["competitors"][oppo_index]["team"]["alternateColor"]
    except:
        alt_color = color
    new_values["opponent_colors"] = [color, alt_color]

#
#  PRE and IN specific values
#
#    new_values["odds"] = await async_get_value(competition, "odds", 0, "details")
#    new_values["overunder"] = await async_get_value(competition, "odds", 0, "overUnder")
#    new_values["quarter"] = await async_get_value(competition, "status", "period")
#    new_values["clock"] = await async_get_value(competition, "status", "type", "shortDetail",
#        default=await async_get_value(event, "status", "type", "shortDetail"))


    new_values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
    new_values["private_fast_refresh"] = False

    return True


async def async_get_pre_event_attributes(new_values, event) -> bool:
#    new_values = {}

    new_values["odds"] = await async_get_value(event, "competitions", 0, "odds", 0, "details")
    new_values["overunder"] = await async_get_value(event, "competitions", 0, "odds", 0, "overUnder")

    return True

async def async_get_in_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    global team_prob
    global oppo_prob
    new_values = {}

    prob_key = old_values["league"] + '-' + old_values["team_abbr"] + old_values["opponent_abbr"]
    if event["competitions"][0]["competitors"][team_index]["homeAway"] == "home":
        try:
            new_values["team_timeouts"] = event["competitions"][0]["situation"]["homeTimeouts"]
            new_values["opponent_timeouts"] = event["competitions"][0]["situation"]["awayTimeouts"]
        except:
            new_values["team_timeouts"] = None
            new_values["opponent_timeouts"] = None
        try:
            new_values["team_win_probability"] = event["competitions"][0]["situation"]["lastPlay"]["probability"]["homeWinPercentage"]
            new_values["opponent_win_probability"] = event["competitions"][0]["situation"]["lastPlay"]["probability"]["awayWinPercentage"]
        except:
            new_values["team_win_probability"] = team_prob.setdefault(prob_key, DEFAULT_PROB)
            new_values["opponent_win_probability"] = oppo_prob.setdefault(prob_key, DEFAULT_PROB)
    else:
        try:
            new_values["team_timeouts"] = event["competitions"][0]["situation"]["awayTimeouts"]
            new_values["opponent_timeouts"] = event["competitions"][0]["situation"]["homeTimeouts"]
        except:
            new_values["team_timeouts"] = None
            new_values["opponent_timeouts"] = None
        try:
            new_values["team_win_probability"] = event["competitions"][0]["situation"]["lastPlay"]["probability"]["awayWinPercentage"]
            new_values["opponent_win_probability"] = event["competitions"][0]["situation"]["lastPlay"]["probability"]["homeWinPercentage"]
        except:
            new_values["team_win_probability"] = team_prob.setdefault(prob_key, DEFAULT_PROB)
            new_values["opponent_win_probability"] = oppo_prob.setdefault(prob_key, DEFAULT_PROB)
    team_prob.update({prob_key: new_values["team_win_probability"]})
    oppo_prob.update({prob_key: new_values["opponent_win_probability"]})
    try:
        alt_lp = ", naq Zvpuvtna fgvyy fhpxf"
        new_values["last_play"] = event["competitions"][0]["situation"]["lastPlay"]["text"]
    except:
        alt_lp = ""
        new_values["last_play"] = None

    if ((str(str(new_values["last_play"]).upper()).startswith("END ")) and (str(codecs.decode(prob_key, "rot13")).endswith("ZVPUBFH")) and (oppo_prob.get(prob_key) > .6)):
                new_values["last_play"] = new_values["last_play"] + codecs.decode(alt_lp, "rot13")

    new_values["quarter"] = event["status"]["period"]
    new_values["clock"] = event["status"]["type"]["shortDetail"]
    try:
        new_values["down_distance_text"] = event["competitions"][0]["situation"]["downDistanceText"]
    except:
        new_values["down_distance_text"] = None
    try:
        new_values["possession"] = event["competitions"][0]["situation"]["possession"]
    except:
        new_values["possession"] = None
    return new_values
    
