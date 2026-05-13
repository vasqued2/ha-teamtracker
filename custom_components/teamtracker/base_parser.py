from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class BaseSportParser(ABC):
    """Base class for all sport data providers."""

    def __init__(self, coordinator: TeamTrackerCoordinator | None = None) -> None:
        # Define the attributes that must be available on all providers
        self._coordinator = coordinator


    @abstractmethod
    #
    #  async_process_event()
    #
    async def async_process_event(self,
        values, sensor_name, data, sport_path, league_id, default_logo, team_id, league_map, lang
    ) -> dict:

        pass                                               # pylint: disable=unnecessary-pass
