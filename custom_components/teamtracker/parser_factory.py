from __future__ import annotations

from typing import TYPE_CHECKING

from .base_parser import BaseSportParser
from .espn_parser import EspnParser

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator


def get_parser(data_format:str, coordinator: TeamTrackerCoordinator) -> BaseSportParser:
    """Factory function to get the correct provider instance."""

    parser: BaseSportParser = EspnParser(coordinator)  # DEFAULT_DATA_FORMAT

    if data_format == "XXX":  # Support other data formats
        pass

    return parser