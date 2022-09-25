""" TeamTracker Team Status """
import logging
from datetime import datetime, timedelta
import arrow
import json
import codecs

import aiohttp
import aiofiles
from async_timeout import timeout
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    DEFAULT_LEAGUE_LOGO,
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

_LOGGER = logging.getLogger(__name__)
team_prob = {}
oppo_prob = {}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    # Print startup message
    _LOGGER.info(
        "TeamTracker version %s is starting, if you have any issues please report them here: %s",
        VERSION,
        ISSUE_URL,
    )
    hass.data.setdefault(DOMAIN, {})

    if entry.unique_id is not None:
        hass.config_entries.async_update_entry(entry, unique_id=None)

        ent_reg = async_get(hass)
        for entity in async_entries_for_config_entry(ent_reg, entry.entry_id):
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=entry.entry_id)

    # Setup the data coordinator
    coordinator = AlertsDataUpdateCoordinator(
        hass,
        entry.data,
        entry.data.get(CONF_TIMEOUT)
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, config_entry):
    """Handle removal of an entry."""
    try:
        await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
        _LOGGER.info("Successfully removed sensor from the " + DOMAIN + " integration")
    except ValueError:
        pass
    return True


async def update_listener(hass, entry):
    """Update listener."""
    entry.data = entry.options
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    hass.async_add_job(hass.config_entries.async_forward_entry_setup(entry, "sensor"))


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry."""
    version = config_entry.version

    # 1-> 2->3: Migration format
    # Add CONF_TIMEOUT, CONF_LEAGUE_ID, CONF_SPORT_PATH, and CONF_LEAGUE_PATH if not already populated
    if version < 3:
        _LOGGER.debug("Migrating from version %s", version)
        updated_config = config_entry.data.copy()

        if CONF_TIMEOUT not in updated_config.keys():
            updated_config[CONF_TIMEOUT] = DEFAULT_TIMEOUT
        if CONF_LEAGUE_ID not in updated_config.keys():
            updated_config[CONF_LEAGUE_ID] = DEFAULT_LEAGUE
        if (CONF_SPORT_PATH not in updated_config.keys()) or (CONF_LEAGUE_PATH not in updated_config.keys()):
            league_id = updated_config[CONF_LEAGUE_ID].upper()
            updated_config[CONF_SPORT_PATH] = DEFAULT_SPORT_PATH
            updated_config[CONF_LEAGUE_PATH] = DEFAULT_LEAGUE_PATH
            for x in range(len(LEAGUE_LIST)):
                if LEAGUE_LIST[x][0] == league_id:
                    updated_config[CONF_SPORT_PATH] = LEAGUE_LIST[x][1]
                    updated_config[CONF_LEAGUE_PATH] = LEAGUE_LIST[x][2]

        if updated_config != config_entry.data:
            hass.config_entries.async_update_entry(config_entry, data=updated_config)

        config_entry.version = 3
        _LOGGER.debug("Migration to version %s complete", config_entry.version)

    return True


class AlertsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TeamTracker data."""

    def __init__(self, hass, config, the_timeout: int):
        """Initialize."""
        self.interval = timedelta(minutes=10)
        self.name = config[CONF_NAME]
        self.timeout = the_timeout
        self.config = config
        self.hass = hass

        _LOGGER.debug("Data will be updated every %s for %s", (self.interval, self.name))

        super().__init__(hass, _LOGGER, name=self.name, update_interval=self.interval)


    async def _async_update_data(self):
        """Fetch data"""
        async with timeout(self.timeout):
            try:
                data = await update_game(self.config)
                # update the interval based on flag
                if data["private_fast_refresh"] == True:
                    self.update_interval = timedelta(seconds=5)
                else:
                    self.update_interval = timedelta(minutes=10)
            except Exception as error:
                raise UpdateFailed(error) from error
            return data
        


async def update_game(config) -> dict:
    """Fetch new state data for the sensor.
    This is the only method that should fetch new data for Home Assistant.
    """

    data = await async_get_state(config)
    return data


async def async_get_state(config) -> dict:
    """Query API for status."""

    values = {}
    headers = {"User-Agent": USER_AGENT, "Accept": "application/ld+json"}
    data = None
    file_override = False

    league_id = config[CONF_LEAGUE_ID].upper()
    sport_path = config[CONF_SPORT_PATH]
    league_path = config[CONF_LEAGUE_PATH]
    url_parms = ""
    if CONF_CONFERENCE_ID in config.keys():
            if (len(config[CONF_CONFERENCE_ID]) > 0):
                url_parms = "?groups=" + config[CONF_CONFERENCE_ID]
                if (config[CONF_CONFERENCE_ID] == '9999'):
                    file_override = True
    team_id = config[CONF_TEAM_ID].upper()
    url = URL_HEAD + sport_path + "/" + league_path + URL_TAIL + url_parms
    
    if (file_override):
        _LOGGER.debug("Overriding API for %s" % team_id)
        async with aiofiles.open('/share/tt/test.json', mode='r') as f:
            contents = await f.read()
        data = json.loads(contents)
    else:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as r:
                _LOGGER.debug("Getting state for %s from %s" % (team_id, url))
                if r.status == 200:
                    data = await r.json()

    values = await async_clear_states(config)
    values["sport"] = sport_path
    values["league"] = league_id
    values["league_logo"] = DEFAULT_LEAGUE_LOGO
    values["team_abbr"] = team_id

    found_team = False
    if data is not None:
        try:
            values["league_logo"] = data["leagues"][0]["logos"][0]["href"]
        except:
            values["league_logo"] = DEFAULT_LEAGUE_LOGO

        for event in data["events"]:
            #_LOGGER.debug("Looking at this event: %s" % event)
            try:
                sn = event["shortName"]
            except:
                sn = ""
                _LOGGER.debug("This is an ill-formed event, it does not have a short name: %s" % event)

            if sn.startswith(team_id + ' ') or sn.endswith(' ' + team_id):
                found_team = True
                _LOGGER.debug("Found event for %s; parsing data.", team_id)
                
                team_index = 0 if event["competitions"][0]["competitors"][0]["team"]["abbreviation"] == team_id else 1
                oppo_index = abs((team_index-1))

                values.update(await async_get_universal_event_attributes(event, team_index, oppo_index))

                if values["state"] in ['PRE']: # odds only exist pre-game
                    values.update(await async_get_pre_event_attributes(event))

                if values["state"] not in ['PRE', 'POST']: # could use status.completed == true as well
                    values.update(await async_get_in_event_attributes(event, values, team_index, oppo_index))
                    if sport_path in ["baseball"]:
                        values.update(await async_get_in_baseball_event_attributes(event, values))
                    elif sport_path in ["soccer"]:
                        values.update(await async_get_in_soccer_event_attributes(event, values, team_index, oppo_index))
                    elif sport_path in ["volleyball"]:
                        values.update(await async_get_in_volleyball_event_attributes(event, values, team_index, oppo_index))
                    elif sport_path in ["hockey"]:
                        values.update(await async_get_in_hockey_event_attributes(event, values, team_index, oppo_index))

                if 'IN' in values["state"]:
                    break
                if 'PRE' in values["state"] and "minute" in values["kickoff_in"]:
                    break

        # Never found the team. Either a bye or a post-season condition
        if not found_team:
            _LOGGER.debug("Did not find a game with for the configured team(%s). Checking if it's a bye week.", team_id)
            found_bye = False
            try: # look for byes in regular season
                for bye_team in data["week"]["teamsOnBye"]:
                    if team_id.lower() == bye_team["abbreviation"].lower():
                        _LOGGER.debug("Bye week confirmed.")
                        found_bye = True
                        values["team_abbr"] = bye_team["abbreviation"]
                        values["team_name"] = bye_team["shortDisplayName"]
                        values["team_logo"] = bye_team["logo"]
                        values["state"] = 'BYE'
                        values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
                if found_bye == False:
                    _LOGGER.debug("Team information (%s) not returned by API: %s" % (team_id, url))
                    values["state"] = 'NOT_FOUND'
                    values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
            except:
                _LOGGER.debug("Team information (%s) not returned by API: %s" % (team_id, url))
                values["state"] = 'NOT_FOUND'
                values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
        if values["state"] == 'PRE' and ((arrow.get(values["date"])-arrow.now()).total_seconds() < 1200):
            _LOGGER.debug("Event is within 20 minutes, setting refresh rate to 5 seconds.")
            values["private_fast_refresh"] = True
        elif values["state"] == 'IN':
            _LOGGER.debug("Event in progress, setting refresh rate to 5 seconds.")
            values["private_fast_refresh"] = True
        elif values["state"] in ['POST', 'BYE']: 
            _LOGGER.debug("Event is over, setting refresh back to 10 minutes.")
            values["private_fast_refresh"] = False
    else:
        _LOGGER.warn("URL did not return data for team (%s):  %s" % (team_id, url))
        values["state"] = 'NOT_FOUND'
        values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
        values["private_fast_refresh"] = False
        
    return values

async def async_clear_states(config) -> dict:
    """Clear all state attributes"""
    new_values = {}

    # Reset values
    new_values = {
        "sport": None,
        "league": None,
        "league_logo": None,
        "team_abbr": None,
        "opponent_abbr": None,

        "date": None,
        "kickoff_in": None,
        "venue": None,
        "location": None,
        "tv_network": None,
        "odds": None,
        "overunder": None,

        "team_name": None,
        "team_id": None,
        "team_record": None,
        "team_rank": None,
        "team_homeaway": None,
        "team_logo": None,
        "team_colors": None,
        "team_score": None,
        "team_win_probability": None,
        "team_timeouts": None,

        "opponent_name": None,
        "opponent_id": None,
        "opponent_record": None,
        "opponent_rank": None,
        "opponent_homeaway": None,
        "opponent_logo": None,
        "opponent_colors": None,
        "opponent_score": None,
        "opponent_win_probability": None,
        "opponent_timeouts": None,

        "quarter": None,
        "clock": None,
        "possession": None,
        "last_play": None,
        "down_distance_text": None,

        "outs": None,
        "balls": None,
        "strikes": None,
        "on_first": None,
        "on_second": None,
        "on_third": None,

        "team_shots_on_target": None,
        "team_total_shots": None,
        "opponent_shots_on_target": None,
        "opponent_total_shots": None,

        "team_sets_won": None,
        "opponent_sets_won": None,

        "last_update": None,
        "private_fast_refresh": False
    }

    return new_values


async def async_get_universal_event_attributes(event, team_index, oppo_index) -> dict:
    """Traverse JSON for universal values"""
    new_values = {}


    new_values["state"] = event["status"]["type"]["state"].upper()
    new_values["date"] = event["date"]
    new_values["kickoff_in"] = arrow.get(event["date"]).humanize()
    new_values["venue"] = event["competitions"][0]["venue"]["fullName"]
    try:
        new_values["location"] = "%s, %s" % (event["competitions"][0]["venue"]["address"]["city"], event["competitions"][0]["venue"]["address"]["state"])
    except:
        try:
            new_values["location"] = event["competitions"][0]["venue"]["address"]["city"]
        except:
            new_values["location"] = None
    try:
        new_values["tv_network"] = event["competitions"][0]["broadcasts"][0]["names"][0]
    except:
        new_values["tv_network"] = None

    new_values["team_abbr"] = event["competitions"][0]["competitors"][team_index]["team"]["abbreviation"]
    new_values["team_id"] = event["competitions"][0]["competitors"][team_index]["team"]["id"]
    new_values["team_name"] = event["competitions"][0]["competitors"][team_index]["team"]["shortDisplayName"]
    try:
        new_values["team_record"] = event["competitions"][0]["competitors"][team_index]["records"][0]["summary"]
    except:
        new_values["team_record"] = None
    try:
        if (event["competitions"][0]["competitors"][team_index]["curatedRank"]["current"] != 99):
            new_values["team_rank"] = event["competitions"][0]["competitors"][team_index]["curatedRank"]["current"] 
    except:
        new_values["team_rank"] = None
    new_values["team_homeaway"] = event["competitions"][0]["competitors"][team_index]["homeAway"]
    new_values["team_logo"] = event["competitions"][0]["competitors"][team_index]["team"]["logo"]
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
    new_values["team_score"] = event["competitions"][0]["competitors"][team_index]["score"]                
    new_values["opponent_abbr"] = event["competitions"][0]["competitors"][oppo_index]["team"]["abbreviation"]
    new_values["opponent_id"] = event["competitions"][0]["competitors"][oppo_index]["team"]["id"]
    new_values["opponent_name"] = event["competitions"][0]["competitors"][oppo_index]["team"]["shortDisplayName"]
    try:
        new_values["opponent_record"] = event["competitions"][0]["competitors"][oppo_index]["records"][0]["summary"]
    except:
        new_values["opponent_record"] = None
    try:
        if (event["competitions"][0]["competitors"][oppo_index]["curatedRank"]["current"] != 99):
            new_values["opponent_rank"] = event["competitions"][0]["competitors"][oppo_index]["curatedRank"]["current"] 
    except:
        new_values["opponent_rank"] = None
    new_values["opponent_homeaway"] = event["competitions"][0]["competitors"][oppo_index]["homeAway"]
    new_values["opponent_logo"] = event["competitions"][0]["competitors"][oppo_index]["team"]["logo"]
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
    new_values["opponent_score"] = event["competitions"][0]["competitors"][oppo_index]["score"]

    new_values["last_update"] = arrow.now().format(arrow.FORMAT_W3C)
    new_values["private_fast_refresh"] = False

    return new_values


async def async_get_pre_event_attributes(event) -> dict:
    """Traverse JSON for PRE event values"""
    new_values = {}


    try:
        new_values["odds"] = event["competitions"][0]["odds"][0]["details"]
    except:
        new_values["odds"] = None
    try:
        new_values["overunder"] = event["competitions"][0]["odds"][0]["overUnder"]
    except:
        new_values["overunder"] = None

    return new_values


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


async def async_get_in_soccer_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}

    new_values["team_shots_on_target"] = 0
    new_values["team_total_shots"] = 0
    for statistic in event["competitions"] [0] ["competitors"] [team_index] ["statistics"]:
        if "shotsOnTarget" in statistic["name"]:
            new_values["team_shots_on_target"] = statistic["displayValue"]
        if "totalShots" in statistic["name"]:
            new_values["team_total_shots"] = statistic["displayValue"]
    new_values["opponent_shots_on_target"] = 0
    new_values["opponent_total_shots"] = 0
    for statistic in event["competitions"] [0] ["competitors"] [oppo_index] ["statistics"]:
        if "shotsOnTarget" in statistic["name"]:
            new_values["opponent_shots_on_target"] = statistic["displayValue"]
        if "totalShots" in statistic["name"]:
            new_values["opponent_total_shots"] = statistic["displayValue"]
                        
    new_values["last_play"] = ''
    for detail in event["competitions"][0]["details"]:
        try:
            mls_team_id = detail["team"]["id"]
                            
            new_values["last_play"] = new_values["last_play"] + "     " + detail["clock"]["displayValue"]
            new_values["last_play"] = new_values["last_play"] + "  " + detail["type"]["text"]
            new_values["last_play"] = new_values["last_play"] + ": " + detail["athletesInvolved"][0]["displayName"]
            if mls_team_id == old_values["team_id"]:
                new_values["last_play"] = new_values["last_play"] + " (" + old_values["team_abbr"] + ")"
            else:
                new_values["last_play"] = new_values["last_play"] + " (" + old_values["opponent_abbr"] + ")          "
        except:
            new_values["last_play"] = new_values["last_play"] + " (Last play not found) "
    return new_values


async def async_get_in_volleyball_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}


    new_values["clock"] = event["status"]["type"]["detail"] # Set
    new_values["team_sets_won"] = old_values["team_score"]
    new_values["opponent_sets_won"] = old_values["opponent_score"]
    try:
        new_values["team_score"] = event["competitions"] [0] ["competitors"] [team_index] ["linescores"] [-1] ["value"]
    except:
        new_values["team_score"] = 0
    try:
        new_values["opponent_score"] = event["competitions"] [0] ["competitors"] [oppo_index] ["linescores"] [-1] ["value"]
    except:
        new_values["opponent_score"] = 0
                            
    new_values["last_play"] = ''
    try:
        sets = len(event["competitions"] [0] ["competitors"] [team_index] ["linescores"])
    except:
        sets = 0
    for x in range (0, sets):
        new_values["last_play"] = new_values["last_play"] + " Set " + str(x + 1) + ": "
        new_values["last_play"] = new_values["last_play"] + old_values["team_abbr"] + " "
        try:
            new_values["last_play"] = new_values["last_play"] + str(int(event["competitions"] [0] ["competitors"] [team_index] ["linescores"] [x] ["value"])) + " "
        except:
            new_values["last_play"] = new_values["last_play"] + "?? "
        new_values["last_play"] = new_values["last_play"] + old_values["opponent_abbr"] + " "
        try:
            new_values["last_play"] = new_values["last_play"] + str(int(event["competitions"] [0] ["competitors"] [oppo_index] ["linescores"] [x] ["value"])) + "; "
        except:
            new_values["last_play"] = new_values["last_play"] + "??; "

    return new_values


async def async_get_in_hockey_event_attributes(event, old_values, team_index, oppo_index) -> dict:
    """Get IN event values"""
    new_values = {}

    new_values["clock"] = event["status"]["type"]["shortDetail"] # Period clock

    new_values["team_shots_on_target"] = 0
    for statistic in event["competitions"] [0] ["competitors"] [oppo_index] ["statistics"]:
        _LOGGER.debug("Looking at this statistic: %s" % statistic)
        if "saves" in statistic["name"]:
            shots = int(old_values["team_score"]) + int(statistic["displayValue"])
            new_values["team_shots_on_target"] = str(shots)

    new_values["opponent_shots_on_target"] = 0
    for statistic in event["competitions"] [0] ["competitors"] [team_index] ["statistics"]:
        _LOGGER.debug("Looking at this statistic: %s" % statistic)
        if "saves" in statistic["name"]:
            shots = int(old_values["opponent_score"]) + int(statistic["displayValue"])
            new_values["opponent_shots_on_target"] = str(shots)
            
    return new_values
