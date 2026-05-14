""" Parser Factory """
from __future__ import annotations

from typing import TYPE_CHECKING

from .provider_base import BaseSportProvider
from .provide_espn import EspnProvider
from .provide_espn_all import EspnAllLeaguesProvider
from .provide_hockeytech import HockeyTechProvider
from .utils import is_integer

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator


def get_provider(sport_path: str, league_path: str, team_id: str="", coordinator: TeamTrackerCoordinator | None = None) -> BaseSportProvider:
    """Factory function to get the correct provider instance."""

    provider: BaseSportProvider = EspnProvider(coordinator)

    if sport_path.lower() == "hockeytech":
        provider = HockeyTechProvider(coordinator)
    elif league_path.lower() == "all" and is_integer(team_id):
        provider = EspnAllLeaguesProvider(coordinator)

    return provider