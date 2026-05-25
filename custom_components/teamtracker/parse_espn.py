""" Parse ESPN JSON response """
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import logging
import re
from typing import TYPE_CHECKING

import arrow

from .const import API_LIMIT, DEFAULT_LOGO
from .models import TeamTrackerValues
from .parser_base import BaseSportParser
from .set_values import SetValuesMixin
from .utils import get_value

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

_LOGGER = logging.getLogger(__name__)



class EspnParser(BaseSportParser, SetValuesMixin):
    """Class to parse responses in ESPN JSON format."""

    def __init__(self) -> None:
        # Define the attributes that must be available on all providers
        super().__init__()
        self._lang = ""
        self._search_key = ""
        self._stop_flag = False
        self._found_competitor = False
        self._event_state = "NOT_FOUND"
        self._prev_values: TeamTrackerValues



    def setup(self,
        sensor_name: str,
        sport_path: str,
        league_path: str,
        league_id: str,
        team_id: str,
    ) -> bool:
        self._sensor_name = sensor_name
        self._sport_path = sport_path
        self._league_path = league_path
        self._league_id = league_id
        self._default_logo = DEFAULT_LOGO
        self._team_id = team_id.upper()

        return True




    def parse_response(
        self,
        provider_response, 
        lang: str
    ) -> TeamTrackerValues:
        """Loop throught the json data returned by the API to find the right event and set values"""


        rc = self.initialize_sensor_values(provider_response)
        if rc is False:
            return self._values

        data = provider_response["data"]

        self._lang = lang
        self._search_key = self._team_id

        self._prev_values = TeamTrackerValues()

        self._stop_flag = False
        self._found_competitor = False


        self._values.league_logo = get_value(
            data, "leagues", 0, "logos", 0, "href", default=DEFAULT_LOGO
        )
        self._values.league_name = get_value(
            data, "leagues", 0, "name", default=""
        )

        events = data.get("events", [])
        limit_hit = len(events) == API_LIMIT
        first_date = datetime(9999, 12, 31, 1, 0, 0)
        last_date = datetime(1900, 1, 31, 1, 0, 0)

        for event in events:
            self._event_state = "NOT_FOUND"
            grouping_index = -1
            for grouping_index, grouping in enumerate(
                get_value(event, "groupings", default=[])
            ):

                competition_index = -1
                for competition_index, competition in enumerate(
                    get_value(grouping, "competitions", default=[])
                ):
                    first_date, last_date = self._process_competition_dates(
                        event,
                        competition,
                        first_date,
                        last_date
                    )

                    rc = self._process_competition(
                        event,
                        grouping_index,
                        competition,
                        competition_index,
                    )
                    if not rc:
                        _LOGGER.debug(
                            "%s: parse_response() Error occurred processing competition: %s",
                            self._sensor_name,
                            self._values,
                        )

                    if self._stop_flag:
                        break
                

            if grouping_index == -1:
                competition_index = -1
                for competition_index, competition in enumerate(
                    get_value(event, "competitions", default=[])
                ):
                    first_date, last_date = self._process_competition_dates(
                        event,
                        competition,
                        first_date,
                        last_date
                    )

                    rc = self._process_competition(
                        event,
                        grouping_index,
                        competition,
                        competition_index,
                    )

                    if self._stop_flag:
                        break
            #
            #  if the competition state is POST but the event state is IN, stop looking
            #    this happens in tennis where an event has many competitions
            #
            if self._values.state == "POST" and self._event_state == "IN":
                self._stop_flag = True
            if self._stop_flag:
                break
            if competition_index == -1:
                _LOGGER.debug(
                    "%s: async_process_event() No competitions for this event: %s",
                    self._sensor_name,
                    get_value(event, "shortName", default="{shortName}"),
                )

        if not self._found_competitor:
            self._competitor_not_found(
                data,
                limit_hit,
                first_date,
                last_date,
                self._team_id,
            )

        rc = self.finalize_sensor_values(provider_response)

        return self._values


    def _process_competition(self,
        event,
        grouping_index,
        competition,
        competition_index,
    ) -> bool:
        """Process a competition"""

        competitor_index = -1
        rc = True

        for competitor_index, competitor in enumerate(
            get_value(competition, "competitors", default=[])
        ):
            matched_index = self._find_search_key(
                event,
                competition,
                competitor,
                competitor_index,
            )


            if matched_index is not None:

                rc = self.process_name_match(
                    event,
                    grouping_index,
                    competition_index,
                    matched_index,
                )
                if not rc:
                    _LOGGER.debug(
                        "%s: async_process_competition() Error occurred processing name match: %s",
                        self._sensor_name,
                        self._values,
                    )
                if self._stop_flag:
                    break
        if competitor_index == -1:
            _LOGGER.debug(
                "%s: async_process_event() No competitors in this competition: %s",
                self._sensor_name,
                str(get_value(competition, "id", default="{id}")),
            )

        return rc


    def process_name_match(self,
        event,
        grouping_index,
        competition_index,
        matched_index,
    )-> bool:
        """Process a name match"""

        self._found_competitor = True
        self._prev_values = replace(self._values)

        self._event_state = str(
            get_value(
                event, "status", "type", "state", default="NOT_FOUND"
            )
        ).upper()

        rc = self._set_values(
            event,
            grouping_index,
            competition_index,
            matched_index,
        )

        if not rc:
            _LOGGER.debug(
                "%s: event() Error occurred setting event values: %s",
                self._sensor_name,
                self._values,
            )

        if self._values.state == "IN":
            self._stop_flag = True
        time_diff = abs(
            (arrow.get(self._values.date) - arrow.now()).total_seconds()
        )
        if self._values.state == "PRE" and time_diff < 1200:
            self._stop_flag = True
        if self._stop_flag:
            return rc

        prev_flag = self._use_prev_values_flag()
        if prev_flag:
            self._values = replace(self._prev_values)

        return rc


    #
    #   _async_find_search_key()
    #
    def _find_search_key(self,
        event,
        competition,
        competitor,
        team_index,
    ):
        """Check if there is a match on wildcard, team_abbreviation, event_name, or athlete_name"""

        if self._search_key == "*":
            _LOGGER.debug(
                "%s: Found competitor using wildcard '%s'; parsing data.",
                self._sensor_name,
                self._search_key,
            )
            return team_index

        if competitor["type"] == "team":
            team_abbreviation = get_value(
                competitor, "team", "abbreviation", default=""
            )
            if self._search_key == team_abbreviation:
                _LOGGER.debug(
                    "%s: Found competition for '%s' in team abbreviation; parsing data.",
                    self._sensor_name,
                    self._search_key,
                )
                return team_index

            team_id = str(get_value(
                competitor, "team", "id", default=""
            ))

            if self._search_key == team_id:
                _LOGGER.debug(
                    "%s: Found competition for team '%s' in team id; parsing data.",
                    self._sensor_name,
                    self._search_key,
                )
                return team_index
                
            team_name = str(get_value(
                competitor, "team", "displayName", default=""
            )).upper()

            try:
                if team_name and re.fullmatch(self._search_key, team_name):
                    _LOGGER.debug(
                        "%s: Found competition for regex '%s' in team.displayName; parsing data.",
                        self._sensor_name,
                        self._search_key,
                    )
                    return team_index
            except re.error as e:
                _LOGGER.warning(
                    "%s: Invalid regular expression '%s' in search key (exception %s)",
                    self._sensor_name,
                    self._search_key,
                    e,
                )
                return None

            roster = str(get_value(
                competitor, "roster", "displayName", default=""
            )).upper()

            try:
                if roster and re.fullmatch(self._search_key, roster):
                    _LOGGER.debug(
                        "%s: Found competition for regex '%s' in roster.displayName; parsing data.",
                        self._sensor_name,
                        self._search_key,
                    )
                    return team_index
            except re.error as e:
                _LOGGER.warning(
                    "%s: Invalid regular expression '%s' in search key (exception %s)",
                    self._sensor_name,
                    self._search_key,
                    e,
                )
                return None

            # Abbreviations in event_name can be different than team_abbr so look there if neither team abbrevations match
            team0_abbreviation = str(
                get_value(
                    competition, "competitors", 0, "team", "abbreviation", default=""
                )
            )
            if team_index == 1 and self._search_key != team0_abbreviation:
                event_shortname = get_value(event, "shortName", default="")
                if event_shortname.startswith(self._search_key + " ") or event_shortname.endswith(
                    " " + self._search_key
                ):
                    self._values.api_message = (
                        "team_id '"
                        + self._search_key
                        + "' does not match team_abbr.  Found in event_name."
                    )
                    _LOGGER.warning(
                        "%s: Found competition for '%s' in event_name; parsing data.  Rebuild sensor using team_abbr for better performance.",
                        self._sensor_name,
                        self._search_key,
                    )
                    return team_index  # Don't know what team to match so use this one
            return None

        if competitor["type"] == "athlete":
            athlete_name = str(
                get_value(competitor, "athlete", "displayName", default="")
            ).upper()
            try:
                if self._search_key in athlete_name or re.fullmatch(self._search_key, athlete_name):
                    _LOGGER.debug(
                        "%s: Found competition for '%s' in athlete name; parsing data",
                        self._sensor_name,
                        self._search_key,
                    )
                    return team_index
            except re.error as e:
                _LOGGER.warning(
                    "%s: Invalid regular expression '%s' in search key (exception %s)",
                    self._sensor_name,
                    self._search_key,
                    e,
                )
            return None

        _LOGGER.debug(
            "%s: Unexpected competitor type found '%s'",
            self._sensor_name,
            competitor["type"],
        )

        return None

    #
    #   _async_use_prev_values_flag()
    #
    def _use_prev_values_flag(self):
        """Determine if prev_values should be saved"""

    #
    #   If the state or prev_state is POST or IN and > 18 hrs in the future, treat is as PRE
    #     This can happen if an event is postponed
    #
        current_state = self._values.state
        if current_state in ("POST", "IN"):
            time_diff = (arrow.get(self._values.date) - arrow.now()).total_seconds()
            if time_diff > 64800:
                current_state = "PRE"
        prev_state = self._prev_values.state
        if prev_state in ("POST", "IN"):
            time_diff = (arrow.get(self._prev_values.date) - arrow.now()).total_seconds()
            if time_diff > 64800:
                prev_state = "PRE"


        if prev_state == "POST":
            if current_state == "PRE":
                # Use POST if PRE is more than 18 hours in future
                time_diff = (arrow.get(self._values.date) - arrow.now()).total_seconds()
                if time_diff > 64800:
                    return True
            elif current_state == "POST":
                # use POST w/ latest date
                if arrow.get(self._prev_values.date) > arrow.get(self._values.date):
                    return True
                if self._sport_path in ["golf", "racing"] and (
                    arrow.get(self._prev_values.date) == arrow.get(self._values.date)
                ):
                    return True
        if prev_state == "PRE":
            if current_state == "PRE":
                # use PRE w/ earliest date
                if arrow.get(self._prev_values.date) <= arrow.get(self._values.date):
                    return True
            elif current_state == "POST":
                # Use PRE if less than 18 hours in future
                time_diff = abs(
                    arrow.get(self._prev_values.date) - arrow.now()
                ).total_seconds()
                if time_diff < 64800:
                    return True

        return False

    #
    #  _competitor_not_found()
    #
    def _competitor_not_found(self,
        data,
        limit_hit,
        first_date,
        last_date,
        team_id,
    ):
        """Handle messaging if competitor was not found"""

        if limit_hit:
            self._values.api_message = (
                "API_LIMIT hit.  No competition found for '"
                + team_id
                + "' between "
                + first_date.strftime("%Y-%m-%dT%H:%MZ")
                + " and "
                + last_date.strftime("%Y-%m-%dT%H:%MZ")
            )
            _LOGGER.debug(
                "%s: API_LIMIT hit (%s).  No competitor information '%s' returned by API",
                self._sensor_name,
                API_LIMIT,
                self._search_key,
            )
            return

        if self._sport_path == "racing":
            events = data.get("events")

            event_name = get_value(
                events, 0, "shortName", default=None
            )
            event_date = get_value(
                events, 0, "date", default=None
            )
            if event_name is not None:
                competitors = get_value(
                    events, 0, "competitions", 0, "competitors", default=None
                )
                if competitors is None:
                    self._values.event_name = event_name
                    self._values.date = event_date
                    self._values.api_message = f"Drivers not found, qualifying not complete for {event_name}"
                    _LOGGER.debug(
                        "%s: No drivers found for %s",
                        self._sensor_name,
                        event_name,
                    )
                    return

        self._values.api_message = (
            "No competition scheduled for '"
            + team_id
            + "' between "
            + first_date.strftime("%Y-%m-%dT%H:%MZ")
            + " and "
            + last_date.strftime("%Y-%m-%dT%H:%MZ")
        )
        _LOGGER.debug(
            "%s: No competitor information '%s' returned by API",
            self._sensor_name,
            self._search_key,
        )

        return


    def _process_competition_dates(self,
        event,
        competition,
        first_date,
        last_date
    ) -> tuple[datetime, datetime]:
        """Process dates"""

        competition_date_str = get_value(
            competition, "date", default=(get_value(event, "date"))
        )
        try:
            competition_date = datetime.fromisoformat(
                str(competition_date_str).replace("Z", "+00:00")
            ).replace(tzinfo=None)
            last_date = max(last_date, competition_date)
            first_date = min(first_date, competition_date)
        except (ValueError, TypeError):
            pass

        return first_date, last_date
