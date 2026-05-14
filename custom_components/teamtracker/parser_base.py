""" Base class for all parsers """
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator

class BaseSportParser(ABC):
    """Base class for all sport data providers."""

    def __init__(self) -> None:
        # Define the attributes that must be available on all providers
        pass

    @abstractmethod
    #
    #  setup()
    #
    def setup(self,
        sensor_name, sport_path, league_id, team_id
    ) -> bool:
        pass


    @abstractmethod
    #
    #  async_process_event()
    #
    async def async_parse_response(self,
        values, data, league_map, lang
    ) -> dict:

        pass                                               # pylint: disable=unnecessary-pass
