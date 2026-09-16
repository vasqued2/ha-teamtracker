"""Resilient wrapper for ESPN soccer/all scoreboard failures."""
from __future__ import annotations

from typing import Any

from .provide_espn_all import EspnAllLeaguesProvider


class ResilientEspnAllLeaguesProvider(EspnAllLeaguesProvider):
    """Keep soccer/all fallbacks usable when ESPN scoreboard data is missing."""

    async def async_call_espn_api(
        self,
        hass,
        base_url,
        params,
        sensor_name,
        team_id,
        file_override=False,
    ) -> dict[str, Any]:
        """Normalize only failed scoreboard payloads to an empty event mapping."""
        response = await super().async_call_espn_api(
            hass,
            base_url,
            params,
            sensor_name,
            team_id,
            file_override,
        )

        if "/scoreboard" not in str(base_url):
            return response

        if isinstance(response, dict) and isinstance(response.get("data"), dict):
            return response

        normalized = dict(response) if isinstance(response, dict) else {}
        normalized["data"] = {}
        normalized.setdefault("url", None)
        normalized.setdefault("timestamp", None)
        return normalized
