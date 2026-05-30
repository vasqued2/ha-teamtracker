""" Parser factory """

from __future__ import annotations

from typing import TYPE_CHECKING

from .parse_cflscoreboard import CflScoreboardParser
from .parse_espn import EspnParser
from .parse_espn_all import EspnAllParser
from .parse_hockeytech import HockeyTechParser
from .parser_base import BaseSportParser
from .provide_cflscoreboard import CFL_DATA_FORMAT
from .provide_espn import ESPN_DATA_FORMAT
from .provide_espn_all import ESPNALL_DATA_FORMAT
from .provide_hockeytech import HT_DATA_FORMAT

if TYPE_CHECKING:
    from .coordinator import TeamTrackerCoordinator


def get_parser(data_format:str, coordinator: TeamTrackerCoordinator) -> BaseSportParser:
    """Factory function to get the correct provider instance."""

    parser = BaseSportParser(coordinator) # Base parser only populate foundational attributes

    if data_format == CFL_DATA_FORMAT:
        parser = CflScoreboardParser(coordinator)
    elif data_format == ESPN_DATA_FORMAT:
        parser = EspnParser(coordinator)
    elif data_format == ESPNALL_DATA_FORMAT:
        parser = EspnAllParser(coordinator)
    elif data_format == HT_DATA_FORMAT:
        parser = HockeyTechParser(coordinator)
    else:
        parser = BaseSportParser(coordinator)

    return parser