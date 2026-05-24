""" Parser factory """

from __future__ import annotations

from typing import TYPE_CHECKING

from .parse_cflscoreboard import CflScoreboardParser
from .parse_espn import EspnParser
from .parse_hockeytech import HockeyTechParser
from .parser_base import BaseSportParser
from .provide_cflscoreboard import CFL_DATA_FORMAT
from .provide_hockeytech import HT_DATA_FORMAT

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator


def get_parser(data_format:str) -> BaseSportParser:
    """Factory function to get the correct provider instance."""

    parser: BaseSportParser = EspnParser()  # DEFAULT_DATA_FORMAT

    if data_format == CFL_DATA_FORMAT:
        parser = CflScoreboardParser()
    elif data_format == HT_DATA_FORMAT:
        parser = HockeyTechParser()

    return parser