""" Parser factory """

from __future__ import annotations

from typing import TYPE_CHECKING

from .parser_base import BaseSportParser
from .parse_espn import EspnParser

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator


def get_parser(data_format:str) -> BaseSportParser:
    """Factory function to get the correct provider instance."""

    parser: BaseSportParser = EspnParser()  # DEFAULT_DATA_FORMAT

    if data_format == "XXX":  # Support other data formats
        pass

    return parser