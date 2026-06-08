""" Parse CFL Scoreboard JSON response """
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from typing import TYPE_CHECKING

import arrow

from .const import DEFAULT_LOGO
from .models import TeamTrackerValues
from .parser_base import BaseSportParser
from .utils import get_value

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

_LOGGER = logging.getLogger(__name__)
DEFAULT_COLORS = ["#D3D3D3", "#A9A9A9"]

class CflScoreboardParser(BaseSportParser):
    """Class to parse responses in ESPN JSON format."""

    def __init__(self, coordinator: TeamTrackerCoordinator) -> None:
        # Define the attributes that must be available on all providers
        super().__init__(coordinator)
        self._lang = ""
        self._search_key = ""
        self._stop_flag = False
        self._found_competitor = False
        self._event_state = "NOT_FOUND"
        self._prev_values: TeamTrackerValues

        self._team_side = ""
        self._opponent_side = ""


    #
    #  initialize_values()
    #    Set sensor attributes that do not rely on the API
    #
    def initialize_sensor_values(self, provider_response) -> bool:
        rc = super().initialize_sensor_values(provider_response)
        self._values.sport = "football"

        return rc


    def setup(self,
        sensor_name: str,
        sport_path: str,
        league_path: str,
        league_id: str,
        team_id: str,
    ) -> bool:
        rc = super().setup(sensor_name, sport_path, league_path, league_id, team_id)
        self._default_logo = DEFAULT_LOGO

        return rc


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

        weekly_schedule = self._get_current_schedule(data)
        week_name =  get_value(weekly_schedule, "name", default="")
        first_date_str =  get_value(weekly_schedule, "startDate", default="")
        last_date_str =  get_value(weekly_schedule, "endDate", default="")

        tournaments = get_value(weekly_schedule, "tournaments", default=[])

        tournament = self._get_tournament(tournaments, self._team_id)

        if tournament:
            rc = self._set_values(weekly_schedule, tournament)
            if rc is False:
                _LOGGER.debug(
                    "%s: Error parsing response for '%s' for CFL '%s'",
                    self._sensor_name,
                    self._search_key,
                    week_name
                )
        else:
            first_date = datetime.fromisoformat(str(first_date_str)).replace(tzinfo=None)
            last_date = datetime.fromisoformat(str(last_date_str)).replace(tzinfo=None)

            self._values.api_message = (
                "No competition scheduled for '"
                + str(self._values.team_abbr)
                + "' in CFL '"
                + week_name
                + "' between "
                + first_date.strftime("%Y-%m-%dT%H:%MZ")
                + " and "
                + last_date.strftime("%Y-%m-%dT%H:%MZ")
            )
            _LOGGER.debug(
                "%s: No competitor information '%s' returned by API for %s",
                self._sensor_name,
                self._search_key,
                week_name
            )

        rc = self.finalize_sensor_values(provider_response)

        return self._values



    #
    #  _get_current_schedule()
    #
    def _get_current_schedule(self, rounds) -> dict:
        """Return the tournaments for the current active or recently completed round."""
        if not rounds:
            return {}

        # Get the current time in ISO format to match the API's timezone-aware strings
        # The API uses '+00:00', which aligns with UTC
        now = datetime.utcnow()
        
        # Calculate the cutoff timestamp (24 hours ago) in ISO format
        cutoff_time = now - timedelta(hours=24)
        cutoff_iso = cutoff_time.isoformat() + "+00:00"

        r = {}
        for r in rounds:
            status = r.get("status", "").lower()
            end_date = r.get("endDate", "")

            # 1. Condition: The round is explicitly not complete (e.g., 'playing' or 'scheduled')
            if status != "complete":
                return r

            # 2. Condition: The round is complete, but it ended within the last 24 hours
            if end_date and end_date >= cutoff_iso:
                return r

        # 3. Fallback Condition: If all rounds are complete and past the 24h window,
        # return the very last round item in the list so the sensor doesn't go blank.
        return r[-1]


    #
    #   _get_tournament()
    #
    def _get_tournament(self,
        tournaments,
        search_key,
    ) -> dict: 
        """Check if there is a match on wildcard, team_abbreviation, event_name, or athlete_name"""

        for t in tournaments:
            for side in ("home", "away"):
                self._team_side = side
                self._opponent_side = "away" if side == "home" else "home"

                if search_key == "*":
                    _LOGGER.debug(
                        "%s: Found competitor using wildcard '%s'; parsing data.",
                        self._sensor_name,
                        search_key,
                    )
                    return t

                team_id = str(get_value(
                    t, f"{side}Squad", "id", default=""
                ))
                if search_key == team_id:
                    _LOGGER.debug(
                        "%s: Found competition for '%s' in team id; parsing data.",
                        self._sensor_name,
                        search_key,
                    )
                    return t

                team_abbr = get_value(
                    t, f"{side}Squad", "shortName", default=""
                )
                if search_key == team_abbr:
                    _LOGGER.debug(
                        "%s: Found competition for '%s' in team shortName; parsing data.",
                        self._sensor_name,
                        search_key,
                    )
                    return t
                    
                team_name = str(get_value(
                    t, f"{side}Squad", "name", default=""
                )).upper()

                try:
                    if team_name and re.fullmatch(search_key, team_name):
                        _LOGGER.debug(
                            "%s: Found competition for regex '%s' in team name; parsing data.",
                            self._sensor_name,
                            search_key,
                        )
                        return t
                except re.error as e:
                    _LOGGER.warning(
                        "%s: Invalid regular expression '%s' in search key (exception %s)",
                        self._sensor_name,
                        search_key,
                        e,
                    )
                    return {}

        return {}


    #
    #  Set Values
    #
    def _set_values(
        self,
        schedule,
        tournament
    ) -> bool:

        status = get_value(tournament, "status", default="")
        if status.lower() == "complete":
            self._values.state = "POST"
        elif status.lower() == "scheduled":
            self._values.state = "PRE"
        else:
            self._values.state = "IN"

        self._values.season = get_value(schedule, "type", default="")

        # Event Details
        self._values.team_abbr = get_value(tournament, f"{self._team_side}Squad", "shortName", default="")
        self._values.opponent_abbr = get_value(tournament, f"{self._opponent_side}Squad", "shortName", default="")
        away = get_value(tournament, "awaySquad", "shortName", default="{shortName}")
        home = get_value(tournament, "homeSquad", "shortName", default="{shortName}")
        self._values.event_name = f"{away}@{home}"                
        self._values.event_id = get_value(tournament, "cflId", default=None)
        self._values.event_id = None if (self._values.event_id is None) else str(self._values.event_id)
        self._values.date = get_value(tournament, "date")
        self._values.kickoff_in = arrow.get(self._values.date).humanize(locale=self._lang)
        self._values.series_summary = None
        self._values.venue = None
        self._values.location = None
        self._values.tv_network = None
        odds = get_value(tournament, "markets", "away", "value", default="")
        self._values.odds = f"{self._values.team_abbr} {odds}"
        self._values.overunder = None

        # Team Data
        self._values.team_name = get_value(tournament, f"{self._team_side}Squad", "name", default="")
        self._values.team_long_name = self._values.team_name
        self._values.team_id = str(get_value(tournament, f"{self._team_side}Squad", "id", default=""))
        self._values.team_record = None
        self._values.team_rank = None
        self._values.team_conference_id = None
        self._values.team_homeaway = self._team_side
        self._values.team_logo = None
        self._values.team_url = None
        self._values.team_colors = DEFAULT_COLORS
        self._values.team_score = get_value(tournament, f"{self._team_side}Squad", "score")
        self._values.team_win_probability = None
        winner = str(get_value(tournament, "winner", default=""))
        self._values.team_winner = (winner == self._values.team_id)
        self._values.team_timeouts = get_value(tournament, "timeouts", f"{self._team_side}")

        # Opponent Data
        self._values.opponent_name = get_value(tournament, f"{self._opponent_side}Squad", "name", default="")
        self._values.opponent_long_name = self._values.opponent_name
        self._values.opponent_id = str(get_value(tournament, f"{self._opponent_side}Squad", "id", default=""))
        self._values.opponent_record = None
        self._values.opponent_rank = None
        self._values.opponent_conference_id = None
        self._values.opponent_homeaway = self._opponent_side
        self._values.opponent_logo = None
        self._values.opponent_url = None
        self._values.opponent_colors = DEFAULT_COLORS
        self._values.opponent_score = get_value(tournament, f"{self._opponent_side}Squad", "score")
        self._values.team_win_probability = None
        winner = str(get_value(tournament, "winner", default=""))
        self._values.opponent_winner = (winner == self._values.opponent_id)
        self._values.opponent_timeouts = get_value(tournament, "timeouts", f"{self._opponent_side}")

        # In Game Attributes
        self._values.quarter = get_value(tournament, "activePeriod")
        self._values.clock = get_value(tournament, "clock")
        possession = str(get_value(tournament, "possession", "")).lower()
        if possession == self._team_side:
            self._values.possession = self._values.team_id
        elif possession == self._opponent_side:
            self._values.possession = self._values.opponent_id
        else:
            self._values.possession = None
        self._values.last_play = None
        self._values.down_distance_text = None

        # Baseball Specific
        self._values.outs = None
        self._values.balls = None
        self._values.strikes = None
        self._values.on_first = None
        self._values.on_second = None
        self._values.on_third = None

        # Soccer/Hockey
        self._values.team_shots_on_target = None
        self._values.team_total_shots = None
        self._values.opponent_shots_on_target = None
        self._values.opponent_total_shots = None

        # Volleyball
        self._values.team_sets_won = None
        self._values.opponent_sets_won = None

        # System/API Metadata
        if self._values.state == "IN":
            self._values.private_fast_refresh = True

        return True
