""" Parse CFL Scoreboard JSON response """
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
import logging
from typing import TYPE_CHECKING

import arrow
import jmespath

from .const import DEFAULT_LOGO
from .models import TeamTrackerValues
from .parser_base import BaseSportParser
from .utils import get_value, is_integer, lookup_actual_team_id

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

_LOGGER = logging.getLogger(__name__)
DEFAULT_COLORS = ["#D3D3D3", "#A9A9A9"]


#
#  MlbStatsParser()
#    Parser for the MLB Stats API json
#
class MlbStatsParser(BaseSportParser):
    """Class to parse responses in MLB Stats format."""

    def __init__(self, coordinator: TeamTrackerCoordinator) -> None:
        """ Initialize the MLB Stats parser"""
        super().__init__(coordinator)
        self._lang = ""
        self._search_key = ""
        self._stop_flag = False
        self._found_competitor = False
        self._event_state = "NOT_FOUND"
        self._prev_values: TeamTrackerValues


    #
    #  initialize_values()
    #    Set sensor attributes that do not rely on the API
    #    Override the sport to baseball from the sport_path.
    #
    def initialize_sensor_values(self, provider_response) -> bool:
        rc = super().initialize_sensor_values(provider_response)
        self._values.sport = "baseball"

        return rc


    #
    #  setup()
    #
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


    #
    #  parse_response()
    #
    def parse_response(
        self,
        provider_response, 
        lang: str
    ) -> TeamTrackerValues:
        """Loop throught the json data returned by the API to find the right event and set values"""

        rc = self.initialize_sensor_values(provider_response)
        if rc is False:
            _LOGGER.debug(
                "%s: Error initalizing sensor values for '%s' from MLB Stats",
                self._sensor_name,
                self._search_key,
            )
            return self._values

        data = provider_response["data"]
        team_list = provider_response.get("lookups", {}).get("team_list", [])
        self._lang = lang

        # Incoming team_id is either a team_id or a search term to find the team_id
        #   Searches must be done w/ the actual team_id or a '*'
        self._search_key = self._team_id
        if self._team_id != "*" and not is_integer(self._team_id):
            self._search_key = lookup_actual_team_id(self._sensor_name, self._team_id, team_list)

        # If the  response contains gamePk, the response is a live game
        live_game_pk = get_value(data, "gamePk", default=None)
        if live_game_pk:
            rc = self._set_live_values(data)
        else:
            game = self._get_current_game(data)
            if game:
                rc = self._set_values(game, team_list)
            else:
                dates = data.get("dates", None)
                first_date_str =  dates[0].get("date", None) if dates else None
                last_date_str =  dates[-1].get("date", None) if dates else None

                if dates is None or first_date_str is None or last_date_str is None:

                    today = datetime.now(timezone.utc)
                    self._values.api_message = (
                        "No upcoming competitions scheduled for league '"
                        + str(self._league_path)
                        + "' in MLB Stats on "
                        + today.strftime("%Y-%m-%dT%H:%MZ")
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

        if rc is False:
            _LOGGER.debug(
                "%s: Error parsing response for '%s' from MLB Stats",
                self._sensor_name,
                self._search_key,
            )
        rc = self.finalize_sensor_values(provider_response)

        return self._values


    #
    #  _get_current_game()
    #
    def _get_current_game(self, data) -> dict | None:
        """Return the tournaments for the current active or recently completed round."""


        def game_starts_soon(game: dict) -> bool:
            """Return True if the game starts within 12 hours."""
            game_time = datetime.fromisoformat(
                game["gameDate"].replace("Z", "+00:00")
            )

            return game_time - datetime.now(UTC) <= timedelta(hours=12)


        if not data:
            return None

        game = None

        # Handle wild card
        if self._search_key == "*":
            queries = [
                "sort_by(dates[].games[?status.abstractGameState=='Live'][], &gameDate)[0]",
                "sort_by(dates[].games[?status.abstractGameState=='Preview'][], &gameDate)[0]",
                "reverse(sort_by(dates[].games[?status.abstractGameState=='Final'][], &gameDate))[0]",
            ]
            for query in queries:
                game = jmespath.search(query, data)
                if game:
                    break
            return game

        # Return the first live game matching search_key
        live_query = f"""
        sort_by(dates[].games[?status.abstractGameState == 'Live' &&
            (teams.home.team.id == `{self._search_key}` ||
            teams.away.team.id == `{self._search_key}`)][], &gameDate)[0]
        """
        # Return the all preview games matching search_key
        preview_query = f"""
        sort_by(dates[].games[?status.abstractGameState == 'Preview' &&
            (teams.home.team.id == `{self._search_key}` || 
            teams.away.team.id == `{self._search_key}`)][], &gameDate)
        """
        # Return the last complete game matching search_key
        final_query = f"""
        reverse(sort_by(dates[].games[?status.abstractGameState == 'Final' &&
            (teams.home.team.id == `{self._search_key}` ||
            teams.away.team.id == `{self._search_key}`)][], &gameDate))[0]
        """

        live_game = jmespath.search(live_query, data)
        if live_game:
            return live_game

        preview_games = jmespath.search(preview_query, data) or []
        # Find first preview game starting soon
        for game in preview_games:
            if game_starts_soon(game):
                return game

        final_game = jmespath.search(final_query, data)
        if final_game:
            return final_game

        # No preview within 12 hours, return earliest preview if one exists
        if preview_games:
            return preview_games[0]

        return game


    #
    #  _set_values()
    #
    def _set_values(
        self,
        game: dict,
        team_list
    ) -> bool:
        """ Set values for for PRE and POST games """

        away_id = str(get_value(game, "teams", "away", "team", "id", default=""))
        if away_id == self._search_key:
            team_side = "away"
            opponent_side = "home"
        else:
            team_side = "home"
            opponent_side = "away"

        status = get_value(game, "status", "abstractGameState", default="")
        if status.lower() == "preview":
            self._values.state = "PRE"
        elif status.lower() == "live":
            self._values.state = "IN"
        else:
            self._values.state = "POST"

        self._values.season = get_value(game, "gameType", default="")

        self._values.team_id = str(get_value(game, "teams", team_side, "team", "id", default=""))
        self._values.opponent_id = str(get_value(game, "teams", opponent_side, "team", "id", default=""))

        # Must get abbreviations from the team_list lookup table
        team_abbr = None
        opponent_abbr = None
        if isinstance(team_list, list):
            team_abbr = next(
                (team["abbreviation"] for team in team_list if team["id"] == self._values.team_id),
                None,  # returned if not found
            )
            opponent_abbr = next(
                (team["abbreviation"] for team in team_list if team["id"] == self._values.opponent_id),
                None,  # returned if not found
            )

        # Event Details
        if team_side == "home":
            self._values.event_name = f"{opponent_abbr}@{team_abbr}"
        else:
            self._values.event_name = f"{team_abbr}@{opponent_abbr}"

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

        self._values.team_abbr = team_abbr
        self._values.team_name = get_value(game, "teams", team_side, "team", "name", default="")
        self._values.team_long_name = self._values.team_name

        wins = str(get_value(game, "teams", team_side, "leagueRecord", "wins", default="0"))
        losses = str(get_value(game, "teams", team_side, "leagueRecord", "losses", default="0"))
        ties = str(get_value(game, "teams", team_side, "leagueRecord", "ties", default="0"))
        if ties == "0":
            self._values.team_record = f"{wins}-{losses}"
        else:
            self._values.team_record = f"{wins}-{losses}-{ties}"
        self._values.team_rank = None
        self._values.team_conference_id = None
        self._values.team_homeaway = team_side
        self._values.team_logo = None
        self._values.team_url = None
        self._values.team_colors = DEFAULT_COLORS
        self._values.team_score = str(get_value(game, "teams", team_side, "score", default=""))
        self._values.team_win_probability = None
        self._values.team_winner = get_value(game, "teams", team_side, "isWinner")
        self._values.team_timeouts = None

        # Opponent Data
        self._values.opponent_abbr = opponent_abbr
        self._values.opponent_name = get_value(game, "teams", opponent_side, "team", "name", default="")
        self._values.opponent_long_name = self._values.opponent_name

        wins = str(get_value(game, "teams", opponent_side, "leagueRecord", "wins", default="0"))
        losses = str(get_value(game, "teams", opponent_side, "leagueRecord", "losses", default="0"))
        ties = str(get_value(game, "teams", opponent_side, "leagueRecord", "ties", default="0"))
        if ties == "0":
            self._values.opponent_record = f"{wins}-{losses}"
        else:
            self._values.opponent_record = f"{wins}-{losses}-{ties}"
        self._values.opponent_rank = None
        self._values.opponent_conference_id = None
        self._values.opponent_homeaway = opponent_side
        self._values.opponent_logo = None
        self._values.opponent_url = None
        self._values.opponent_colors = DEFAULT_COLORS
        self._values.opponent_score = str(get_value(game, "teams", opponent_side, "score", default=""))
        self._values.opponent_win_probability = None
        self._values.opponent_winner = get_value(game, "teams", opponent_side, "isWinner")
        self._values.opponent_timeouts = None

        # In Game Attributes
        self._values.quarter = None
        self._values.clock = get_value(game, "status", "detailedState")
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
    #  _set_live_values()
    #
    def _set_live_values(
        self,
        game: dict,
    ) -> bool:
        """ Set values for for IN games """

        away_id = str(get_value(game, "gameData", "teams", "away", "id", default=""))
        if away_id == self._search_key:
            team_side = "away"
            opponent_side = "home"
        else:
            team_side = "home"
            opponent_side = "away"

        self._values.state = "IN"
        self._values.season = get_value(game, "gameData", "game", "type", default="")

        # Event Details
        self._values.team_abbr = get_value(game, "gameData", "teams", team_side, "abbreviation", default="{abbreviation}")
        self._values.opponent_abbr = get_value(game, "gameData", "teams", opponent_side, "abbreviation", default="{abbreviation}")
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
        self._values.team_name = get_value(game, "gameData", "teams", team_side, "teamName", default="")
        self._values.team_long_name = get_value(game, "gameData", "teams", team_side, "name", default="")
        self._values.team_id = str(get_value(game, "gameData", "teams", team_side, "id", default=""))
        wins = str(get_value(game, "gameData", "teams", team_side, "record", "leagueRecord", "wins", default="0"))
        losses = str(get_value(game, "gameData", "teams", team_side, "record", "leagueRecord", "losses", default="0"))
        ties = str(get_value(game, "gameData", "teams", team_side, "record", "leagueRecord", "ties", default="0"))
        if ties == "0":
            self._values.team_record = f"{wins}-{losses}"
        else:
            self._values.team_record = f"{wins}-{losses}-{ties}"
        self._values.team_rank = None
        self._values.team_conference_id = get_value(game, "gameData", "teams", team_side, "division", "name", default="")
        self._values.team_homeaway = team_side
        self._values.team_logo = None
        self._values.team_url = None
        self._values.team_colors = DEFAULT_COLORS
        self._values.team_score = str(get_value(game, "liveData", "linescore", "teams", team_side, "runs"))
        self._values.team_win_probability = None
        self._values.team_winner = None
        self._values.team_timeouts = None

        # Opponent Data
        self._values.opponent_name = get_value(game, "gameData", "teams", opponent_side, "teamName", default="")
        self._values.opponent_long_name = get_value(game, "gameData", "teams", opponent_side, "name", default="")
        self._values.opponent_id = str(get_value(game, "gameData", "teams", opponent_side, "id", default=""))
        wins = str(get_value(game, "gameData", "teams", opponent_side, "record", "leagueRecord", "wins", default="0"))
        losses = str(get_value(game, "gameData", "teams", opponent_side, "record", "leagueRecord", "losses", default="0"))
        ties = str(get_value(game, "gameData", "teams", opponent_side, "record", "leagueRecord", "ties", default="0"))
        if ties == "0":
            self._values.opponent_record = f"{wins}-{losses}"
        else:
            self._values.opponent_record = f"{wins}-{losses}-{ties}"
        self._values.opponent_rank = None
        self._values.opponent_conference_id = get_value(game, "gameData", "teams", opponent_side, "division", "name", default="")
        self._values.opponent_homeaway = opponent_side
        self._values.opponent_logo = None
        self._values.opponent_url = None
        self._values.opponent_colors = DEFAULT_COLORS
        self._values.opponent_score = str(get_value(game, "liveData", "linescore", "teams", opponent_side, "runs"))
        self._values.opponent_win_probability = None
        self._values.opponent_winner = None
        self._values.opponent_timeouts = None

        # In Game Attributes
        self._values.quarter = get_value(game, "liveData", "linescore", "currentInning")
        inning = get_value(game, "liveData", "linescore", "currentInningOrdinal")
        inning_state = get_value(game, "liveData", "linescore", "inningState")
        self._values.clock = f"{inning_state} {inning}"
        if self._values.clock[:3].lower() in ["bot", "mid"]:
            self._values.possession = str(get_value(game, "gameData", "teams", "home", "id", default=""))
        else:
            self._values.possession = str(get_value(game, "gameData", "teams", "away", "id", default=""))

        self._values.down_distance_text = None

        # Baseball Specific
        rc = self._set_current_play(game)

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

        return rc


    #
    #  _set_current_play
    #
    def _set_current_play(
        self,
        game: dict,
    ) -> bool:
        """Set base runners, pitch count, and last play attributes"""

        # Set the base runners
        player = get_value(game, "liveData", "plays", "currentPlay", "matchup", "postOnFirst","id", default=None)
        self._values.on_first = (player is not None)
        player = get_value(game, "liveData", "plays", "currentPlay", "matchup", "postOnSecond","id", default=None)
        self._values.on_second = (player is not None)
        player = get_value(game, "liveData", "plays", "currentPlay", "matchup", "postOnThird","id", default=None)
        self._values.on_third = (player is not None)

        # If there is a description of the result of the last play, use that
        description = get_value(game, "liveData", "plays", "currentPlay", "result", "description", default=None)
        if description:
            self._values.last_play = f"{description}"
            self._values.outs = get_value(game, "liveData", "plays", "currentPlay", "count", "outs", default=None)
            self._values.balls = get_value(game, "liveData", "plays", "currentPlay", "count", "balls", default=None)
            self._values.strikes = get_value(game, "liveData", "plays", "currentPlay", "count", "strikes", default=None)
            return True

        # If there are events in the event list, use that
        self._values.last_play = None
        play_events = get_value(game, "liveData", "plays", "currentPlay", "playEvents", default=[])
        if len(play_events) > 0:
            last_event = play_events[-1]

            self._values.outs = get_value(last_event, "count", "outs", default=None)
            self._values.balls = get_value(last_event, "count", "balls", default=None)
            self._values.strikes = get_value(last_event, "count", "strikes", default=None)

            # Generate Last Play
            description = get_value(last_event, "details", "description", default=False)
            is_pitch = get_value(last_event, "isPitch", default=False)
            if is_pitch:
                pitch_number = get_value(last_event, "pitchNumber", default="")
                pitcher = get_value(game, "liveData", "plays", "currentPlay", "matchup", "pitcher", "fullName", default="")
                batter = get_value(game, "liveData", "plays", "currentPlay", "matchup", "batter", "fullName", default="")
                self._values.last_play = f"{pitcher} pitches to {batter}: Pitch {pitch_number} - {description}"
            else:
                self._values.last_play = f"{description}"
            return True

        # Fall back to the list of all plays
        self._values.outs = get_value(game, "liveData", "linescore", "outs", default=None)
        self._values.balls = get_value(game, "liveData", "linescore", "balls", default=None)
        self._values.strikes = get_value(game, "liveData", "linescore", "strikes", default=None)

        all_plays = get_value(game, "liveData", "plays", "allPlays", default=[])
        if len(all_plays) > 1:
            last_play = all_plays[-2]
            self._values.last_play = get_value(last_play, "result", "description", default=None)

        return True


