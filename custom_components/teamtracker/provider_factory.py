""" Parser Factory """
from __future__ import annotations

from typing import TYPE_CHECKING

from .provide_cflscoreboard import CflScoreboardProvider
from .provide_espn import EspnProvider
from .provide_espn_all import EspnAllLeaguesProvider
from .provide_hockeytech import HockeyTechProvider
from .provide_livetennis import (
    DATA_PROVIDER_LIVETENNIS,
    LiveTennisProvider,
    resolve_api_key,
)
from .provide_mlbstats import MlbStatsProvider
from .provider_base import BaseSportProvider
from .utils import is_integer

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator


def get_provider(sport_path: str, league_path: str, team_id: str="", coordinator: TeamTrackerCoordinator | None = None) -> BaseSportProvider:
    """Factory function to get the correct provider instance."""

    provider: BaseSportProvider = EspnProvider(coordinator)

    if sport_path.lower() == "hockeytech":
        provider = HockeyTechProvider(coordinator)
    elif sport_path.lower() == "cflscoreboard":
        provider = CflScoreboardProvider(coordinator)
    elif sport_path.lower() == "mlbstats":
        provider = MlbStatsProvider(coordinator)
    elif sport_path.lower() == DATA_PROVIDER_LIVETENNIS and resolve_api_key(
        coordinator.hass if coordinator else None, league_path
    ):
        # The Live Tennis API needs a key.  Without one there is nothing to
        # select, so fall through and leave behavior exactly as it was.
        provider = LiveTennisProvider(coordinator)
    elif league_path.lower() == "all" and is_integer(team_id):
        provider = EspnAllLeaguesProvider(coordinator)

    return provider