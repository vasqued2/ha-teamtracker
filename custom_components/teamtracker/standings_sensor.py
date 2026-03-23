"""Standings sensor for TeamTracker — shows a full league table as attributes."""
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DEFAULT_ICON, DOMAIN, SPORT_ICON_MAP

_LOGGER = logging.getLogger(__name__)


class TeamTrackerStandingsSensor(CoordinatorEntity, SensorEntity):
    """Sensor that exposes a full league standings table via attributes.

    State  = abbreviation of the first-place team (or number of entries as fallback).
    Attributes:
        standings  – list of dicts, one per team: rank, points, wins, losses, …
        league     – league ID (e.g. "BUND")
        sport      – sport path (e.g. "soccer")
        last_update
    """

    def __init__(
        self,
        coordinator,
        entry_id: str,
        name: str,
        sport_path: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._name = name
        self._icon = SPORT_ICON_MAP.get(sport_path, DEFAULT_ICON)

    @property
    def unique_id(self) -> str:
        return f"standings_{self._entry_id}"

    @property
    def name(self) -> str:
        return self._name

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def state(self) -> str | None:
        if not self.coordinator.data:
            return None
        standings = self.coordinator.data.get("standings", [])
        if not standings:
            return None
        leader = next((t for t in standings if t.get("rank") == 1), standings[0])
        return leader.get("team_abbr") or str(len(standings))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        data = self.coordinator.data
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "standings":      data.get("standings", []),
            "league":         data.get("league"),
            "sport":          data.get("sport"),
            "last_update":    data.get("last_update"),
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success
