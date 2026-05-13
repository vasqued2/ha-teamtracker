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
    #  async_parse_data()
    #
    async def async_parse_data(self, data) -> dict:
        """Updates sensor values using data returned by API or in cache"""

        pass                                               # pylint: disable=unnecessary-pass
