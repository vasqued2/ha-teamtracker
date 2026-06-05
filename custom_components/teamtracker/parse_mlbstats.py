""" Parse CFL Scoreboard JSON response """
from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import TYPE_CHECKING

import arrow

from .const import DEFAULT_LAST_UPDATE, DEFAULT_LOGO
from .models import TeamTrackerValues
from .parser_base import BaseSportParser
from .utils import get_value, is_integer

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

_LOGGER = logging.getLogger(__name__)
DEFAULT_COLORS = ["#D3D3D3", "#A9A9A9"]

class MlbStatsParser(BaseSportParser):
    """Class to parse responses in MLB Stats format."""

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
        self._values.sport = "baseball"

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
        team_list = provider_response.get("lookups", {}).get("team_list", [])

        live_game_pk = get_value(data, "gamePk", default=None)
        if live_game_pk:
            # Need to determine team and away sides
            self._team_side = "home"
            self._opponent_side = "away"
            rc = self._set_live_values(data)
            rc = self.finalize_sensor_values(provider_response)

            return self._values

        self._lang = lang
        if self._team_id == "*" or is_integer(self._team_id):
            self._search_key = self._team_id
        else:
            self._search_key = self._get_integer_team_id(self._team_id, team_list)

        first_date_str =  data.get("dates", [])[0].get("date", DEFAULT_LAST_UPDATE)
        last_date_str =  data.get("dates", [])[-1].get("date", DEFAULT_LAST_UPDATE)


        game = self._get_current_game(data)
        if game:
            rc = self._set_values(game)
            if rc is False:
                _LOGGER.debug(
                    "%s: Error parsing response for '%s' from MLB Stats",
                    self._sensor_name,
                    self._search_key,
                )
        else:
            first_date = datetime.fromisoformat(str(first_date_str)).replace(tzinfo=None)
            last_date = datetime.fromisoformat(str(last_date_str)).replace(tzinfo=None)

            self._values.api_message = (
                "No competition scheduled for '"
                + str(self._values.team_abbr)
                + "' in MLB Stats between "
                + first_date.strftime("%Y-%m-%dT%H:%MZ")
                + " and "
                + last_date.strftime("%Y-%m-%dT%H:%MZ")
            )
            _LOGGER.debug(
                "%s: No competitor information '%s' returned by MLB Stats API",
                self._sensor_name,
                self._search_key,
            )

        rc = self.finalize_sensor_values(provider_response)

        return self._values


    #
    #  _get_integer_team_id()
    #
    def _get_integer_team_id(self, 
        team_id: str, 
        team_list: list
    ) -> str:
        """Return the integer team_id."""

        if team_list:
            try:
                integer_team_id = next(
                    (team["id"] for team in team_list 
                        if ((self._team_id == team.get("abbreviation", "")) or
                            (re.fullmatch(self._team_id, team.get("displayName", ""))) or
                            (re.fullmatch(self._team_id, team.get("location", "")))
                        )
                    ), 
                    team_id
                )
                return str(integer_team_id)
            except re.error as e:
                _LOGGER.warning(
                    "%s: Invalid regular expression '%s' in search key (exception %s)",
                    self._sensor_name,
                    self._search_key,
                    e,
                )

        return team_id



    #
    #  _get_current_game()
    #
    def _get_current_game(self, data) -> dict | None:
        """Return the tournaments for the current active or recently completed round."""

        if not data:
            return None

        daily_schedule = {}
        schedule = get_value(data, "dates", default={})
        for daily_schedule in schedule:
            games = daily_schedule.get("games", {})
            for game in games:
                team_id = str(get_value(game, "teams", "home", "team", "id", default=""))
                if self._search_key in (team_id, "*"):
                    self._team_side = "home"
                    self._opponent_side = "away"
                    return game
                team_id = str(get_value(game, "teams", "away", "team", "id", default=""))
                if (self._search_key in (team_id)):
                    self._team_side = "away"
                    self._opponent_side = "home"
                    return game
        return None


    #
    #  Set Values
    #
    def _set_values(
        self,
        game: dict,
    ) -> bool:

        status = get_value(game, "status", "abstractGameState", default="")
        if status.lower() == "preview":
            self._values.state = "PRE"
        elif status.lower() == "live":
            self._values.state = "IN"
        else:
            self._values.state = "POST"

        self._values.season = get_value(game, "gameType", default="")

        # Event Details
        self._values.team_abbr = get_value(game, self._team_side, "shortName", default="{shortName}")
        self._values.opponent_abbr = get_value(game, self._opponent_side, "shortName", default="{shortName}")
        away = get_value(game, "away", "shortName", default="{shortName}")
        home = get_value(game, "home", "shortName", default="{shortName}")
        self._values.event_name = f"{away}@{home}"                
        self._values.event_id = get_value(game, "gamePk", default=None)
        self._values.event_id = None if (self._values.event_id is None) else str(self._values.event_id)
        self._values.date = get_value(game, "gameDate")
        try:
            self._values.kickoff_in = arrow.get(self._values.date).humanize(locale=self._lang)
        except:
            try:
                self._values.kickoff_in = arrow.get(self._values.date).humanize(
                    locale=self._lang[:2]
                )
            except:
                self._values.kickoff_in = arrow.get(self._values.date).humanize()
        self._values.series_summary = None
        self._values.venue = get_value(game, "venue", "name", default=None)
        self._values.location = None
        self._values.tv_network = None
        self._values.odds = None
        self._values.overunder = None

        # Team Data
        self._values.team_name = get_value(game, "teams", self._team_side, "team", "name", default="")
        self._values.team_long_name = self._values.team_name
        self._values.team_id = str(get_value(game, "teams", self._team_side, "team", "id", default=""))
        wins = str(get_value(game, "teams", self._team_side, "leagueRecord", "wins", default="0"))
        losses = str(get_value(game, "teams", self._team_side, "leagueRecord", "losses", default="0"))
        ties = str(get_value(game, "teams", self._team_side, "leagueRecord", "ties", default="0"))
        if ties == "0":
            self._values.team_record = f"{wins}-{losses}"
        else:
            self._values.team_record = f"{wins}-{losses}-{ties}"
        self._values.team_rank = None
        self._values.team_conference_id = None
        self._values.team_homeaway = self._team_side
        self._values.team_logo = None
        self._values.team_url = None
        self._values.team_colors = DEFAULT_COLORS
        self._values.team_score = str(get_value(game, "teams", self._team_side, "score"))
        self._values.team_win_probability = None
        self._values.team_winner = get_value(game, "teams", self._team_side, "isWinner")
        self._values.team_timeouts = None

        # Opponent Data
        self._values.opponent_name = get_value(game, "teams", self._opponent_side, "team", "name", default="")
        self._values.opponent_long_name = self._values.opponent_name
        self._values.opponent_id = str(get_value(game, "teams", self._team_side, "team", "id", default=""))
        wins = str(get_value(game, "teams", self._opponent_side, "leagueRecord", "wins", default="0"))
        losses = str(get_value(game, "teams", self._opponent_side, "leagueRecord", "losses", default="0"))
        ties = str(get_value(game, "teams", self._opponent_side, "leagueRecord", "ties", default="0"))
        if ties == "0":
            self._values.opponent_record = f"{wins}-{losses}"
        else:
            self._values.opponent_record = f"{wins}-{losses}-{ties}"
        self._values.opponent_rank = None
        self._values.opponent_conference_id = None
        self._values.opponent_homeaway = self._opponent_side
        self._values.opponent_logo = None
        self._values.opponent_url = None
        self._values.opponent_colors = DEFAULT_COLORS
        self._values.opponent_score = str(get_value(game, "teams", self._team_side, "score"))
        self._values.team_win_probability = None
        self._values.opponent_winner = get_value(game, "teams", self._team_side, "isWinner")
        self._values.opponent_timeouts = None

        # In Game Attributes
        self._values.quarter = None
        self._values.clock = None
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


    #
    #  _set_live_values
    #
    def _set_live_values(
        self,
        game: dict,
    ) -> bool:

        self._values.state = "IN"
        self._values.season = get_value(game, "gameData", "game", "type", default="")

        # Event Details
        self._values.team_abbr = get_value(game, "gameData", "teams", self._team_side, "abbreviation", default="{abbreviation}")
        self._values.opponent_abbr = get_value(game, "gameData", "teams", self._opponent_side, "abbreviation", default="{abbreviation}")
        away = get_value(game, "gameData", "teams", "away", "abbreviation", default="{abbreviation}")
        home = get_value(game, "gameData", "teams", "home", "abbreviation", default="{abbreviation}")
        self._values.event_name = f"{away}@{home}"                
        self._values.event_id = get_value(game, "gamePk", default=None)
        self._values.event_id = None if (self._values.event_id is None) else str(self._values.event_id)
        self._values.date = get_value(game, "gameData", "datetime", "dateTime")
        try:
            self._values.kickoff_in = arrow.get(self._values.date).humanize(locale=self._lang)
        except:
            try:
                self._values.kickoff_in = arrow.get(self._values.date).humanize(
                    locale=self._lang[:2]
                )
            except:
                self._values.kickoff_in = arrow.get(self._values.date).humanize()
        self._values.series_summary = None
        self._values.venue = get_value(game, "gameData", "venue", "name", default="")
        city = get_value(game, "gameData", "venue", "location", "city", default="")
        state = get_value(game, "gameData", "venue", "location", "stateAbbrev", default="")
        country = get_value(game, "gameData", "venue", "location", "country", default="")
        self._values.location = f"{city}, {state}, {country}"
        self._values.tv_network = None
        self._values.odds = None
        self._values.overunder = None

        # Team Data
        self._values.team_name = get_value(game, "gameData", "teams", self._team_side, "teamName", default="")
        self._values.team_long_name = get_value(game, "gameData", "teams", self._team_side, "name", default="")
        self._values.team_id = str(get_value(game, "gameData", "teams", self._team_side, "id", default=""))
        wins = str(get_value(game, "gameData", "teams", self._team_side, "record", "leagueRecord", "wins", default="0"))
        losses = str(get_value(game, "gameData", "teams", self._team_side, "record", "leagueRecord", "losses", default="0"))
        ties = str(get_value(game, "gameData", "teams", self._team_side, "record", "leagueRecord", "ties", default="0"))
        if ties == "0":
            self._values.team_record = f"{wins}-{losses}"
        else:
            self._values.team_record = f"{wins}-{losses}-{ties}"
        self._values.team_rank = None
        self._values.team_conference_id = get_value(game, "gameData", "teams", self._team_side, "division", "name", default="")
        self._values.team_homeaway = self._team_side
        self._values.team_logo = None
        self._values.team_url = None
        self._values.team_colors = DEFAULT_COLORS
        self._values.team_score = str(get_value(game, "liveData", "linescore", "teams", self._team_side, "runs"))
        self._values.team_win_probability = None
        self._values.team_winner = None
        self._values.team_timeouts = None

        # Opponent Data
        self._values.opponent_name = get_value(game, "gameData", "teams", self._opponent_side, "teamName", default="")
        self._values.opponent_long_name = get_value(game, "gameData", "teams", self._opponent_side, "name", default="")
        self._values.opponent_id = str(get_value(game, "gameData", "teams", self._opponent_side, "id", default=""))
        wins = str(get_value(game, "gameData", "teams", self._opponent_side, "record", "leagueRecord", "wins", default="0"))
        losses = str(get_value(game, "gameData", "teams", self._opponent_side, "record", "leagueRecord", "losses", default="0"))
        ties = str(get_value(game, "gameData", "teams", self._opponent_side, "record", "leagueRecord", "ties", default="0"))
        if ties == "0":
            self._values.opponent_record = f"{wins}-{losses}"
        else:
            self._values.opponent_record = f"{wins}-{losses}-{ties}"
        self._values.opponent_rank = None
        self._values.opponent_conference_id = get_value(game, "gameData", "teams", self._opponent_side, "division", "name", default="")
        self._values.opponent_homeaway = self._opponent_side
        self._values.opponent_logo = None
        self._values.opponent_url = None
        self._values.opponent_colors = DEFAULT_COLORS
        self._values.opponent_score = str(get_value(game, "liveData", "linescore", "teams", self._opponent_side, "runs"))
        self._values.team_win_probability = None
        self._values.opponent_winner = None
        self._values.opponent_timeouts = None

        # In Game Attributes
        self._values.quarter = get_value(game, "liveData", "linescore", "currentInning")
        inning = get_value(game, "liveData", "linescore", "currentInningOrdinal")
        inningHalf = get_value(game, "liveData", "linescore", "inningHalf")
        self._values.clock = f"{inningHalf} {inning}"
        if inningHalf.lower == "top":
            self._values.possession = self._values.opponent_id
        else:
            self._values.possession = self._values.team_id

        all_plays = get_value(game, "liveData", "plays", "allPlays", default=[])
        if len(all_plays) >= 2:
            last_play = all_plays[-2]
            self._values.last_play = get_value(last_play, "result", "description", default=None)
        else:
            self._values.last_play = None

        self._values.down_distance_text = None

        # Baseball Specific
        self._values.outs = get_value(game, "liveData", "plays", "currentPlay", "count", "outs", default=None)
        self._values.balls = get_value(game, "liveData", "plays", "currentPlay", "count", "balls", default=None)
        self._values.strikes = get_value(game, "liveData", "plays", "currentPlay", "count", "strikes", default=None)
        player = get_value(game, "liveData", "plays", "currentPlay", "matchup", "postOnFirst","id", default=None)
        self._values.on_first = player is not None
        player = get_value(game, "liveData", "plays", "currentPlay", "matchup", "postOnSecond","id", default=None)
        self._values.on_second = player is not None
        player = get_value(game, "liveData", "plays", "currentPlay", "matchup", "postOnThird","id", default=None)
        self._values.on_third = player is not None

        # Soccer/Hockey
        self._values.team_shots_on_target = None
        self._values.team_total_shots = None
        self._values.opponent_shots_on_target = None
        self._values.opponent_total_shots = None

        # Volleyball
        self._values.team_sets_won = None
        self._values.opponent_sets_won = None

        # System/API Metadata
        self._values.private_fast_refresh = True

        return True
