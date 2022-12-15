import arrow
import logging
from datetime import date, datetime, timedelta

from .const import (
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TIMEOUT,
    CONF_TEAM_ID,
    COORDINATOR,
    DEFAULT_CONFERENCE_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_LEAGUE,
    DEFAULT_LOGO,
    DEFAULT_LEAGUE_PATH,
    DEFAULT_PROB,
    DEFAULT_SPORT_PATH,
    DOMAIN,
    ISSUE_URL,
    LEAGUE_LIST,
    PLATFORMS,
    URL_HEAD,
    URL_TAIL,
    USER_AGENT,
    VERSION,
)

from .set_values import (
    async_set_values,
)
from .clear_values import (
    async_clear_values,
)
_LOGGER = logging.getLogger(__name__)

async def async_process_event(sensor_name, data, sport_path, league_id, DEFAULT_LOGO, team_id, lang, url) -> dict:
    values = {} 
    prev_values = {}

    stop_flag = False

    values = await async_clear_values()

    search_key = team_id
    sport = sport_path
    
    values["sport"] = sport_path
    values["league"] = league_id
    values["team_abbr"] = team_id
    values["state"] = 'NOT_FOUND'
    values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
    values["private_fast_refresh"] = False

    found_competitor = False
    if data is not None:
        try:
            values["league_logo"] = data["leagues"][0]["logos"][0]["href"]
        except:
            values["league_logo"] = DEFAULT_LOGO

        for event in data["events"]:
            try:
                comp_index = 0
                for competition in event["competitions"]:
                    if "competitors" not in competition:
                        _LOGGER.debug("%s: No competitors in this competition: %s", sensor_name, competition["id"])
                    else:
                        index = 0
                        for competitor in competition["competitors"]:
                            if competitor["type"] == "team":
                                _LOGGER.debug("%s: Team found in competition for athletes, skipping ID %s", sensor_name, competitor["id"])
                            if competitor["type"] == "athlete":
                                if ((search_key in competitor["athlete"]["displayName"].upper()) or (search_key == "*")):
                                    found_competitor = True
                                    prev_values = values.copy()
                                    if sport in ["golf", "mma", "racing", "tennis"]:
                                        try:
                                            values.update(await async_set_values(values, event, competition, competitor, lang, index, comp_index, sensor_name))
                                        except:
                                            _LOGGER.warn("%s: exception w/ function call", sensor_name)

                                        if values["state"] == "IN":
                                            stop_flag = True;
                                        if ((values["state"] == "PRE") and (abs((arrow.get(values["date"])-arrow.now()).total_seconds()) < 1200)):
                                            stop_flag = True;
                                        if stop_flag:
                                            break;            

                                        if prev_values["state"] == "POST":
                                            if values["state"] == "PRE": # Use POST if PRE is more than 18 hours in future
                                                if (abs((arrow.get(values["date"])-arrow.now()).total_seconds()) > 64800):
                                                                values = prev_values
                                            elif values["state"] == "POST": # use POST w/ latest date
                                                if (arrow.get(prev_values["date"]) > arrow.get(values["date"])):
                                                    values = prev_values
                                                if (arrow.get(prev_values["date"]) == arrow.get(values["date"])) and sport in ["golf", "racing"]:
                                                    values = prev_values
                                        if prev_values["state"] == "PRE":
                                            if values["state"] == "PRE":  # use PRE w/ earliest date
                                                if (arrow.get(prev_values["date"]) <= arrow.get(values["date"])):
                                                    values = prev_values
                                            elif values["state"] == "POST": # Use PRE if less than 18 hours in future
                                                if (abs((arrow.get(prev_values["date"])-arrow.now()).total_seconds()) < 64800):
                                                    values = prev_values

                            index = index + 1

                    if stop_flag:
                        break;
                    comp_index = comp_index + 1
                try:
                    if values["state"] == "POST" and event["status"]["type"]["state"].upper() == "IN":
                        stop_flag = True;
                except:
                    values["state"] = values["state"]
                if stop_flag:
                    break;
            except:
                _LOGGER.debug("%s: No competitions for this event: %s", sensor_name, event["shortName"])

    if found_competitor == False:
        first_date = (date.today() - timedelta(days = 1)).strftime("%Y-%m-%dT%H:%MZ")
        last_date =  (date.today() + timedelta(days = 5)).strftime("%Y-%m-%dT%H:%MZ")
        values["api_message"] = "No competition scheduled for '" + team_id + "' between " + first_date + " and " + last_date
        _LOGGER.debug("%s: Competitor information '%s' not returned by API: %s", sensor_name, team_id, url)

    return values

