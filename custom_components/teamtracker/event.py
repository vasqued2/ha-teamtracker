""" Parse throught the API data and find the right event/competition"""

from datetime import datetime
import logging

import arrow

from .const import API_LIMIT, DEFAULT_LOGO
from .set_values import async_set_values
from .utils import async_get_value

_LOGGER = logging.getLogger(__name__)


async def async_process_event(
    values, sensor_name, data, sport_path, league_id, default_logo, team_id, lang
) -> bool:
    """Loop throught the json data returned by the API to find the right event and set values"""

    prev_values = {}

    stop_flag = False
    search_key = team_id
    sport = sport_path

    found_competitor = False

    values["league_logo"] = await async_get_value(
        data, "leagues", 0, "logos", 0, "href", default=DEFAULT_LOGO
    )

    limit_hit = len(data["events"]) == API_LIMIT
    first_date = datetime(9999, 12, 31, 1, 0, 0)
    last_date = datetime(1900, 1, 31, 1, 0, 0)

    for event in data["events"]:
        event_state = "NOT_FOUND"
        #        _LOGGER.debug("%s: event() Processing event: %s", sensor_name, str(await async_get_value(event, "shortName")))
        competition_index = -1
        for competition_index in range(
            0, len(await async_get_value(event, "competitions", default=[]))
        ):
            competition = await async_get_value(
                event, "competitions", competition_index
            )
            team_index = -1

            competition_date_str = await async_get_value(
                competition, "date", default=(await async_get_value(event, "date"))
            )
            competition_date = datetime.strptime(competition_date_str, "%Y-%m-%dT%H:%Mz")
            if competition_date > last_date:
                last_date = competition_date
            if competition_date < first_date:
                first_date = competition_date
            for team_index in range(
                0, len(await async_get_value(competition, "competitors", default=[]))
            ):
                competitor = await async_get_value(
                    competition, "competitors", team_index
                )
                matched_index = await async_find_search_key(
                    values,
                    sensor_name,
                    search_key,
                    event,
                    competition,
                    competitor,
                    team_index,
                    sport_path
                )

                if matched_index is not None:
                    found_competitor = True
                    prev_values = values.copy()

                    #
                    # Capture the event state because in sports like tennis, it can be different that the competition state
                    #
                    event_state = str(
                        await async_get_value(
                            event, "status", "type", "state", default="NOT_FOUND"
                        )
                    ).upper()
                    rc = await async_set_values(
                        values,
                        event,
                        competition_index,
                        matched_index,
                        lang,
                        sensor_name,
                    )
                    if not rc:
                        _LOGGER.debug(
                            "%s: event() Error occurred setting event values: %s",
                            sensor_name,
                            values,
                        )

                    if values["state"] == "IN":
                        stop_flag = True
                    time_diff = abs(
                        (arrow.get(values["date"]) - arrow.now()).total_seconds()
                    )
                    if values["state"] == "PRE" and time_diff < 1200:
                        stop_flag = True
                    if stop_flag:
                        break

                    prev_flag = await async_use_prev_values_flag(
                        prev_values, values, sensor_name, sport
                    )
                    if prev_flag:
                        values = prev_values

            if team_index == -1:
                _LOGGER.debug(
                    "%s: async_process_event() No competitors in this competition: %s",
                    sensor_name,
                    str(await async_get_value(competition, "id", default="{id}")),
                )
            if stop_flag:
                break
        #
        #  if the competition state is POST but the event state is IN, stop looking
        #    this happens in tennis where an event has many competitions
        #
        if values["state"] == "POST" and event_state == "IN":
            stop_flag = True
        if stop_flag:
            break
        if competition_index == -1:
            _LOGGER.debug(
                "%s: async_process_event() No competitions for this event: %s",
                sensor_name,
                await async_get_value(event, "shortName", default="{shortName}"),
            )

    if not found_competitor:
        if limit_hit:
            values["api_message"] = (
                "API_LIMIT hit.  No competition found for '"
                + team_id
                + "' between "
                + first_date.strftime("%Y-%m-%dT%H:%MZ")
                + " and "
                + last_date.strftime("%Y-%m-%dT%H:%MZ")
            )
            _LOGGER.debug(
                "%s: API_LIMIT hit (%s).  No competitor information '%s' returned by API",
                sensor_name,
                API_LIMIT,
                search_key,
            )
        else:
            values["api_message"] = (
                "No competition scheduled for '"
                + team_id
                + "' between "
                + first_date.strftime("%Y-%m-%dT%H:%MZ")
                + " and "
                + last_date.strftime("%Y-%m-%dT%H:%MZ")
            )
            _LOGGER.debug(
                "%s: No competitor information '%s' returned by API",
                sensor_name,
                search_key,
            )

    return values


async def async_find_search_key(
    values, sensor_name, search_key, event, competition, competitor, team_index, sport_path
):
    """Check if there is a match on wildcard, team_abbreviation, event_name, or athlete_name"""

    if search_key == "*" and (competitor["type"] == "athlete" or sport_path != "tennis"):
        _LOGGER.debug(
            "%s: Found competitor using wildcard '%s'; parsing data.",
            sensor_name,
            search_key,
        )
        return team_index

    if competitor["type"] == "team":
        team_abbreviation = await async_get_value(
            competitor, "team", "abbreviation", default=""
        )
        if search_key == team_abbreviation:
            _LOGGER.debug(
                "%s: Found competition for '%s' in team abbreviation; parsing data.",
                sensor_name,
                search_key,
            )
            return team_index

        # Abbreviations in event_name can be different than team_abbr so look there if neither team abbrevations match
        team0_abbreviation = str(
            await async_get_value(
                competition, "competitors", 0, "team", "abbreviation", default=""
            )
        )
        if team_index == 1 and search_key != team0_abbreviation:
            event_shortname = await async_get_value(event, "shortName", default="")
            if event_shortname.startswith(search_key + " ") or event_shortname.endswith(
                " " + search_key
            ):
                values["api_message"] = (
                    "team_id '"
                    + search_key
                    + "' does not match team_abbr.  Found in event_name."
                )
                _LOGGER.warning(
                    "%s: Found competition for '%s' in event_name; parsing data.  Rebuild sensor using team_abbr for better performance.",
                    sensor_name,
                    search_key,
                )
                return team_index  # Don't know what team to match so use this one
        return None

    if competitor["type"] == "athlete":
        athlete_name = str(
            await async_get_value(competitor, "athlete", "displayName", default="")
        ).upper()
        if search_key in athlete_name:
            _LOGGER.debug(
                "%s: Found competition for '%s' in athlete name; parsing data",
                sensor_name,
                search_key,
            )
            return team_index
        return None

    _LOGGER.debug(
        "%s: Unexpected competitor type found '%s'",
        sensor_name,
        competitor["type"],
    )

    return None


async def async_use_prev_values_flag(prev_values, values, sensor_name, sport):
    """Determine if prev_values should be saved"""

    if prev_values["state"] == "POST":
        if values["state"] == "PRE":
            # Use POST if PRE is more than 18 hours in future
            time_diff = (arrow.get(values["date"]) - arrow.now()).total_seconds()
            if time_diff > 64800:
                return True
        elif values["state"] == "POST":
            # use POST w/ latest date
            if arrow.get(prev_values["date"]) > arrow.get(values["date"]):
                return True
            if sport in ["golf", "racing"] and (
                arrow.get(prev_values["date"]) == arrow.get(values["date"])
            ):
                return True
    if prev_values["state"] == "PRE":
        if values["state"] == "PRE":
            # use PRE w/ earliest date
            if arrow.get(prev_values["date"]) <= arrow.get(values["date"]):
                return True
        elif values["state"] == "POST":
            # Use PRE if less than 18 hours in future
            time_diff = abs(
                arrow.get(prev_values["date"]) - arrow.now()
            ).total_seconds()
            if time_diff < 64800:
                return True

    return False
