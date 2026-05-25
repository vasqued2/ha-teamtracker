""" Baseball specific functionality"""

from .models import TeamTrackerValues
from .utils import get_value


class SetBaseballMixin:
    _values: TeamTrackerValues


    def _set_baseball_values(
        self,
        event, competition_index, team_index
    ) -> bool:
        """Set baseball specific values"""

        self._values.clock = get_value(
            event, "status", "type", "detail"
        )  # Inning
        if not self._values.clock:
            self._values.clock = ""
        if self._values.clock[:3].lower() in ["bot", "mid"]:
            if self._values.team_homeaway in [
                "home"
            ]:  # Home outs, at bat in bottom of inning
                self._values.possession = self._values.team_id
            else:  # Away outs, at bat in bottom of inning
                self._values.possession = self._values.opponent_id
        else:
            if self._values.team_homeaway in [
                "away"
            ]:  # Away outs, at bat in top of inning
                self._values.possession = self._values.team_id
            else:  # Home outs, at bat in top of inning
                self._values.possession = self._values.opponent_id

        self._values.outs = get_value(
            event, "competitions", 0, "situation", "outs"
        )
        self._values.balls = get_value(
            event, "competitions", 0, "situation", "balls"
        )
        self._values.strikes = get_value(
            event, "competitions", 0, "situation", "strikes"
        )
        self._values.on_first = get_value(
            event, "competitions", 0, "situation", "onFirst"
        )
        self._values.on_second = get_value(
            event, "competitions", 0, "situation", "onSecond"
        )
        self._values.on_third = get_value(
            event, "competitions", 0, "situation", "onThird"
        )

        return True