""" Set non-sport specific values """

import codecs
from datetime import date
import logging

import arrow

from .const import (
    DEFAULT_LOGO,
    DEFAULT_PROB,
    GENERAL_RAPID_REFRESH_RATE,
    GENERAL_REFRESH_RATE,
)
from .set_baseball import SetBaseballMixin
from .set_cricket import SetCricketMixin
from .set_golf import SetGolfMixin
from .set_hockey import SetHockeyMixin
from .set_mma import SetMMAMixin
from .set_racing import SetRacingMixin
from .set_soccer import SetSoccerMixin
from .set_tennis import SetTennisMixin
from .set_volleyball import SetVolleyballMixin
from .utils import get_value

_LOGGER = logging.getLogger(__name__)
team_prob: dict[str, float] = {}
oppo_prob: dict[str, float] = {}

class SetValuesMixin(SetBaseballMixin, SetCricketMixin, SetGolfMixin, SetHockeyMixin, SetMMAMixin, SetRacingMixin, SetSoccerMixin, SetTennisMixin, SetVolleyballMixin):
    _sensor_name: str
    _lang: str

#
#  Set Values
#
    def _set_values(
        self,
        event, grouping_index, competition_index, team_index
    ) -> bool:
        """Function to set all new_values for the specified event/competition/team"""

        #    _LOGGER.debug("%s: async_set_values() 1: %s", self._sensor_name, self._sensor_name)

        oppo_index = 1 if team_index == 0 else 0
        grouping = get_value(event, "groupings", grouping_index)
        if grouping is None:
            competition = get_value(event, "competitions", competition_index)
        else:
            competition = get_value(grouping, "competitions", competition_index)
        competitor = get_value(competition, "competitors", team_index)
        opponent = get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            _LOGGER.debug(
                "%s: async_set_values() Invalid competition, competitor, or opponent: %s",
                self._sensor_name,
                self._sensor_name,
            )
            return False

        rc = self._set_universal_values(
            event, grouping_index, competition_index, team_index
        )
        if not rc:
            _LOGGER.debug(
                "%s: async_set_values() Bad rc from async_set_universal_values(): %s",
                self._sensor_name,
                self._sensor_name,
            )
            return False

        #
        #  Additional values only needed for team sports
        #
        if get_value(competitor, "type") == "team":
            rc = self._set_team_values(
                event, grouping_index, competition_index, team_index
            )
            if not rc:
                _LOGGER.debug(
                    "%s: async_set_values() Bad rc from async_set_team_values(): %s",
                    self._sensor_name,
                    self._sensor_name,
                )
                return False

        #    _LOGGER.debug("%s: async_set_values() 3: %s", self._sensor_name, new_values)

        if self._values.state == "PRE":
            rc = self._set_pre_values(event)
            if not rc:
                _LOGGER.debug(
                    "%s: async_set_values() Bad rc from async_set_pre_values(): %s",
                    self._sensor_name,
                    self._sensor_name,
                )
                return False

        if self._values.state == "IN":
            rc = self._set_in_values(
                event, grouping_index, competition_index, team_index
            )
            if not rc:
                _LOGGER.debug(
                    "%s: async_set_values() Bad rc from async_set_in_values(): %s",
                    self._sensor_name,
                    self._sensor_name,
                )
                return False
            #        _LOGGER.debug("%s: async_set_values() 3.1: %s", self._sensor_name, new_values)
            #
            #   Sport Specific Values
            #
            if self._values.sport == "baseball":
                rc = self._set_baseball_values(
                    event, competition_index, team_index
                )
            elif self._values.sport == "soccer":
                rc = self._set_soccer_values(
                    event, competition_index, team_index
                )
            elif self._values.sport == "volleyball":
                rc = self._set_volleyball_values(
                    event, competition_index, team_index
                )
            elif self._values.sport == "hockey":
                rc = self._set_hockey_values(
                    event, competition_index, team_index
                )

        if self._values.sport == "golf":
            rc = self._set_golf_values(
                event, competition_index, team_index
            )
        elif self._values.sport == "tennis":
            rc = self._set_tennis_values(
                event, grouping_index, competition_index, team_index
            )
        elif self._values.sport == "mma":
            rc = self._set_mma_values(
                event, competition_index, team_index
            )
        elif self._values.sport == "racing":
            rc = self._set_racing_values(
                event, competition_index, team_index
            )
        elif self._values.sport == "cricket":
            rc = self._set_cricket_values(
                event, competition_index, team_index
            )

        #    _LOGGER.debug("%s: async_set_values() 4: %s", self._sensor_name, self._sensor_name)
        if not rc:
            _LOGGER.debug(
                "%s: async_set_values() Bad rc from async_set_SPORT_values(): %s",
                self._sensor_name,
                self._sensor_name,
            )
            return False

        self._values.private_fast_refresh = False
        if self._values.state == "IN":
            self._values.private_fast_refresh = True
        if self._values.state == "PRE" and (
            abs((arrow.get(self._values.date) - arrow.now()).total_seconds()) < 
            (int(GENERAL_REFRESH_RATE.total_seconds())*2)
        ):
            _LOGGER.debug(
                "%s: Event is within %s minutes, setting refresh rate to %s seconds.",
                self._sensor_name,
                int(GENERAL_REFRESH_RATE.total_seconds()/60)*2,
                int(GENERAL_RAPID_REFRESH_RATE.total_seconds())
            )
            self._values.private_fast_refresh = True

        #    _LOGGER.debug("%s: async_set_values() 5: %s", self._sensor_name, new_values)

        return rc


    #
    #  Set Universal Values
    #
    def _set_universal_values(
        self,
        event, grouping_index, competition_index, team_index
    ) -> bool:
        """Function to set new_values common for all sports"""

        #    _LOGGER.debug("%s: async_set_universal_values() 1: %s", self._sensor_name, self._sensor_name)

        oppo_index = 1 if team_index == 0 else 0
        grouping = get_value(event, "groupings", grouping_index)
        if grouping is None:
            competition = get_value(event, "competitions", competition_index)
        else:
            competition = get_value(grouping, "competitions", competition_index)
        competitor = get_value(competition, "competitors", team_index)
        opponent = get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            _LOGGER.debug(
                "%s: async_set_universal_values() 1.1: %s", self._sensor_name, self._sensor_name
            )
            return False

        self._values.state = str(
            get_value(
                competition,
                "status",
                "type",
                "state",
                default=get_value(event, "status", "type", "state"),
            )
        ).upper()
        self._values.season = get_value(event, "season", "slug")

        self._values.event_id = get_value(event, "id")
        self._values.event_name = get_value(event, "shortName")
        self._values.event_url = get_value(event, "links", 0, "href")
        self._values.event_stream = get_value(event, "links", 0, "stream")

        self._values.date = get_value(
            competition, "date", default=(get_value(event, "date"))
        )

        #    _LOGGER.debug("%s: async_set_universal_values() 2: %s", self._sensor_name, self._sensor_name)

        try:
            self._values.kickoff_in = arrow.get(self._values.date).humanize(locale=self._lang)
        except:
            try:
                self._values.kickoff_in = arrow.get(self._values.date).humanize(
                    locale=self._lang[:2]
                )
            except:
                self._values.kickoff_in = arrow.get(self._values.date).humanize()

        self._values.series_summary = get_value(
            competition,
            "series",
            "summary",
        )

        self._values.venue = get_value(
            competition,
            "venue",
            "fullName",
            default=get_value(event, "circuit", "fullName"),
        )

        state = get_value(competition, "venue", "address", "state")
        country = get_value(competition, "venue", "address", "country")

        self._values.location = get_value(
            competition, "venue", "address", "city"
        )
        if state:
            if self._values.location:
                self._values.location = f'{self._values.location}, {state}'
            else:
                self._values.location = state
        if country:
            if self._values.location:
                self._values.location = f'{self._values.location}, {country}'
            else:
                self._values.location = country
        if self._values.location is None:
            self._values.location = get_value(
                competition, "venue", "address", "summary"
            )

        #    _LOGGER.debug("%s: async_set_universal_values() 3: %s", self._sensor_name, self._sensor_name)

        broadcasts = get_value(competition, "broadcasts", default=[])
        names = []
        for b in broadcasts:
            b_names = get_value(b, "names", default=[])
            names.extend(b_names)
        self._values.tv_network = "/".join(names) if names else None

        self._values.team_id = get_value(competitor, "id")
        self._values.opponent_id = get_value(opponent, "id")
        #    _LOGGER.debug("%s: async_set_universal_values() 4: %s", self._sensor_name, self._sensor_name)

        self._values.team_name = get_value(
            competitor,
            "team",
            "shortDisplayName",
            default=get_value(competitor, "athlete", "displayName",
                default=get_value(competitor, "roster", "shortDisplayName")
            ),
        )
        self._values.team_long_name = get_value(
            competitor,
            "team",
            "displayName",
            default=get_value(competitor, "athlete", "displayName",
                default=get_value(competitor, "roster", "displayName")
            ),
        )
        self._values.team_conference_id = get_value(
            competitor,
            "team",
            "conferenceId"
        )
        self._values.opponent_name = get_value(
            opponent,
            "team",
            "shortDisplayName",
            default=get_value(opponent, "athlete", "displayName",
                default=get_value(opponent, "roster", "shortDisplayName"),
            ),
        )
        self._values.opponent_long_name = get_value(
            opponent,
            "team",
            "displayName",
            default=get_value(opponent, "athlete", "displayName",
                default=get_value(opponent, "roster", "displayName")
            ),
        )
        self._values.opponent_conference_id = get_value(
            opponent,
            "team",
            "conferenceId"
        )
        self._values.team_record = get_value(
            competitor, "records", 0, "summary"
        )
        self._values.opponent_record = get_value(
            opponent, "records", 0, "summary"
        )

        self._values.team_logo = get_value(
            competitor,
            "team",
            "logo",
            default=get_value(
                competitor, "athlete", "flag", "href", default=DEFAULT_LOGO
            ),
        )
        self._values.opponent_logo = get_value(
            opponent,
            "team",
            "logo",
            default=get_value(
                opponent, "athlete", "flag", "href", default=DEFAULT_LOGO
            ),
        )
        self._values.team_url = get_value(
            competitor,
            "team",
            "links",
            0,
            "href",
            )
        self._values.team_stream = get_value(
            competitor,
            "team",
            "links",
            0,
            "stream",
            )
        self._values.opponent_url = get_value(
            opponent,
            "team",
            "links",
            0,
            "href",
            )
        self._values.opponent_stream = get_value(
            opponent,
            "team",
            "links",
            0,
            "stream",
            )

        #    _LOGGER.debug("%s: async_set_universal_values() 4: %s", self._sensor_name, self._sensor_name)

        self._values.quarter = get_value(
            competition,
            "status",
            "period",
            default=get_value(event, "status", "period"),
        )
        self._values.clock = get_value(
            competition,
            "status",
            "type",
            "shortDetail",
            default=get_value(event, "status", "type", "shortDetail"),
        )
        try:
            self._values.team_score = (
                str(get_value(competitor, "score"))
                + "("
                + str(event["competitions"][0]["competitors"][team_index]["shootoutScore"])
                + ")"
            )
        except:
            self._values.team_score = get_value(competitor, "score")
        try:
            self._values.opponent_score = (
                str(get_value(opponent, "score"))
                + "("
                + str(event["competitions"][0]["competitors"][oppo_index]["shootoutScore"])
                + ")"
            )
        except:
            self._values.opponent_score = get_value(opponent, "score")

        # Some APIs return boolean values as strings, so we need to convert them

        self._values.team_winner = get_value(competitor, "winner")
        if self._values.team_winner == "true":
            self._values.team_winner = True;
        elif self._values.team_winner == "false":
            self._values.team_winner = False;

        self._values.opponent_winner = get_value(opponent, "winner")
        if self._values.opponent_winner == "true":
            self._values.opponent_winner = True;
        elif self._values.opponent_winner == "false":
            self._values.opponent_winner = False;

        self._values.team_rank = get_value(
            competitor, "curatedRank", "current"
        )
        if self._values.team_rank == 99:
            self._values.team_rank = None

        self._values.opponent_rank = get_value(
            opponent, "curatedRank", "current"
        )
        if self._values.opponent_rank == 99:
            self._values.opponent_rank = None

        #    _LOGGER.debug("%s: async_set_universal_values() 5: %s", self._sensor_name, new_values)

        return True

    #
    #  Set Team Values
    #
    def _set_team_values(
        self,
        event, grouping_index, competition_index, team_index
    ) -> bool:
        """Function to set new_values for team sports"""

        #    _LOGGER.debug("%s: async_set_team_values() 1: %s", self._sensor_name, self._sensor_name)

        oppo_index = 1 if team_index == 0 else 0
        grouping = get_value(event, "groupings", grouping_index)
        if grouping is None:
            competition = get_value(event, "competitions", competition_index)
        else:
            competition = get_value(grouping, "competitions", competition_index)

        competitor = get_value(competition, "competitors", team_index)
        opponent = get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            #        _LOGGER.debug("%s: async_set_team_values() 1.1: %s", self._sensor_name, self._sensor_name)
            return False

        #    _LOGGER.debug("%s: async_set_team_values() 2: %s", self._sensor_name, self._sensor_name)

        difference = (date.today() - date(2024, 11, 30))
        alt_series_summary = f"{difference.days:,} qnlf fvapr Zvpuvtna orng Buvb Fgngr"
        #alt_series_summary = None # Cheat code, uncomment in disaster scenarios only

        self._values.team_abbr = get_value(competitor, "team", "abbreviation")
        self._values.opponent_abbr = get_value(
            opponent, "team", "abbreviation"
        )

        #    _LOGGER.debug("%s: async_set_team_values() 3: %s", self._sensor_name, new_values)

        self._values.team_homeaway = get_value(competitor, "homeAway")
        self._values.opponent_homeaway = get_value(opponent, "homeAway")

        team_color = str(
            get_value(competitor, "team", "color", default="D3D3D3")
        )
        oppo_color = str(get_value(opponent, "team", "color", default="A9A9A9"))
        team_alt_color = str(
            get_value(competitor, "team", "alternateColor", default=team_color)
        )
        oppo_alt_color = str(
            get_value(opponent, "team", "alternateColor", default=oppo_color)
        )

        #    _LOGGER.debug("%s: async_set_team_values() 4: %s", self._sensor_name, team_color)

        self._values.team_colors = ["#" + team_color, "#" + team_alt_color]
        self._values.opponent_colors = ["#" + oppo_color, "#" + oppo_alt_color]

        #    _LOGGER.debug("%s: async_set_team_values() 4: %s", self._sensor_name, new_values)

        try:
            if ({str(codecs.decode(str(self._values.sport), "rot13")), 
                str(codecs.decode(str(self._values.team_abbr), "rot13")), 
                str(codecs.decode(str(self._values.opponent_abbr), "rot13"))} == {"sbbgonyy", "BFH", "ZVPU"}
            ):
                if ((self._values.state == "PRE")
                    or ((str(codecs.decode(str(self._values.team_abbr), "rot13")) == "BFH" and self._values.team_winner))
                    or ((str(codecs.decode(str(self._values.opponent_abbr), "rot13")) == "BFH" and self._values.opponent_winner))
                ):
                    if (alt_series_summary):
                        self._values.series_summary = codecs.decode(alt_series_summary, "rot13")
        except (KeyError, TypeError):
            pass  # Key doesn't exist or value is None

        return True


    #
    #  PRE
    #
    def _set_pre_values(self, event) -> bool:
        """Function to set new_values common for PRE state"""

        self._values.odds = get_value(
            event, "competitions", 0, "odds", 0, "details"
        )
        self._values.overunder = get_value(
            event, "competitions", 0, "odds", 0, "overUnder"
        )

        return True


    #
    #  IN
    #
    def _set_in_values(
        self,
        event, grouping_index, competition_index, team_index
    ) -> bool:
        """Function to set new_values common for IN state"""

        #
        #  Pylint doesn't recognize values set by setdefault() method
        #
        global team_prob  # pylint: disable=global-variable-not-assigned
        global oppo_prob  # pylint: disable=global-variable-not-assigned

        #    _LOGGER.debug("%s: async_set_in_values() 1: %s", self._sensor_name, self._sensor_name)

        oppo_index = 1 if team_index == 0 else 0

        grouping = get_value(event, "groupings", grouping_index)
        if grouping is None:
            competition = get_value(event, "competitions", competition_index)
        else:
            competition = get_value(grouping, "competitions", competition_index)

        competitor = get_value(competition, "competitors", team_index)
        opponent = get_value(competition, "competitors", oppo_index)

        if competition is None or competitor is None or opponent is None:
            #        _LOGGER.debug("%s: async_set_in_values() 1.1: %s", self._sensor_name, self._sensor_name)
            return False

        #    _LOGGER.debug("%s: async_set_in_values() 2: %s", self._sensor_name, new_values)

        prob_key = (
            str(self._values.league)
            + "-"
            + str(self._values.team_abbr)
            + str(self._values.opponent_abbr)
        )
        alt_lp = ", naq Zvpuvtna fgvyy fhpxf"
        self._values.down_distance_text = get_value(
            competition, "situation", "downDistanceText"
        )
        self._values.possession = get_value(
            competition, "situation", "possession"
        )

        if str(get_value(competitor, "homeAway")) == "home":
            self._values.team_timeouts = get_value(
                competition, "situation", "homeTimeouts"
            )
            self._values.opponent_timeouts = get_value(
                competition, "situation", "awayTimeouts"
            )
            self._values.team_win_probability = get_value(
                competition,
                "situation",
                "lastPlay",
                "probability",
                "homeWinPercentage",
                default=team_prob.setdefault(prob_key, DEFAULT_PROB),
            )
            self._values.opponent_win_probability = get_value(
                competition,
                "situation",
                "lastPlay",
                "probability",
                "awayWinPercentage",
                default=oppo_prob.setdefault(prob_key, DEFAULT_PROB),
            )
        else:
            self._values.team_timeouts = get_value(
                competition, "situation", "awayTimeouts"
            )
            self._values.opponent_timeouts = get_value(
                competition, "situation", "homeTimeouts"
            )
            self._values.team_win_probability = get_value(
                competition,
                "situation",
                "lastPlay",
                "probability",
                "awayWinPercentage",
                default=team_prob.setdefault(prob_key, DEFAULT_PROB),
            )
            self._values.opponent_win_probability = get_value(
                competition,
                "situation",
                "lastPlay",
                "probability",
                "homeWinPercentage",
                default=oppo_prob.setdefault(prob_key, DEFAULT_PROB),
            )

        #    _LOGGER.debug("%s: async_set_in_values() 4: %s", self._sensor_name, self._sensor_name)

        if self._values.team_win_probability and self._values.opponent_win_probability:
            team_prob.update({prob_key: self._values.team_win_probability})
            oppo_prob.update({prob_key: self._values.opponent_win_probability})
        self._values.last_play = get_value(
            competition, "situation", "lastPlay", "text"
        )

        #    _LOGGER.debug("%s: async_set_in_values() 5: %s", self._sensor_name, self._sensor_name)

        try:
            if ({str(codecs.decode(str(self._values.sport), "rot13")), 
                str(codecs.decode(str(self._values.team_abbr), "rot13")), 
                str(codecs.decode(str(self._values.opponent_abbr), "rot13"))} == {"sbbgonyy", "BFH", "ZVPU"}
            ):
                if (((str(codecs.decode(str(self._values.team_abbr), "rot13")) == "BFH") and (team_prob.get(prob_key, 0.0) >= 0.7))
                    or ((str(codecs.decode(str(self._values.opponent_abbr), "rot13")) == "BFH") and (oppo_prob.get(prob_key, 0.0) >= 0.7))
                ):
                    self._values.last_play = str(self._values.last_play) + codecs.decode(
                        alt_lp, "rot13"
                    )
        except (KeyError, TypeError):
            pass  # Key doesn't exist or value is None

        #    _LOGGER.debug("%s: async_set_in_values() 6: %s", self._sensor_name, self._sensor_name)

        return True