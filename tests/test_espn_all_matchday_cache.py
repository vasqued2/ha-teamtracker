"""Regression tests for ESPN ALL match-day team/schedule caching."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest

from custom_components.teamtracker.provide_espn_all import EspnAllLeaguesProvider


def _provider(cache: dict) -> EspnAllLeaguesProvider:
    provider = object.__new__(EspnAllLeaguesProvider)
    provider.TEAM_SCHEDULE_KEY = "team-schedule-key"
    provider.instance_cache = {provider.TEAM_SCHEDULE_KEY: cache}
    provider.lookups = {}
    provider.DEFAULT_REFRESH_RATE = timedelta(minutes=10)
    provider._coordinator = SimpleNamespace(
        name="PAOK",
        sport_path="soccer",
        league_path="all",
        team_id="605",
        hass=None,
    )
    provider.async_call_espn_api = AsyncMock()
    return provider


def _cache(expires: date, cached_at: datetime | None) -> dict:
    value = {
        "next_game_date": expires,
        "derived_league_name": "Greek Super League",
        "expires": expires,
        "schedule_response": {"data": {"events": []}},
        "team_response": {"data": {"team": {"nextEvent": []}}},
        "next_events": [],
        "sport_path": "soccer",
    }
    if cached_at is not None:
        value["cached_at"] = cached_at
    return value


def _completed_event() -> dict:
    return {
        "id": "paok-aris",
        "date": "2026-09-13T18:00Z",
        "season": {"displayName": "2026-27 Greek Super League"},
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [],
    }


@pytest.mark.asyncio
async def test_future_day_cache_is_reused_without_api_calls():
    with freeze_time("2026-09-13T18:00:00Z"):
        cache = _cache(
            date(2026, 9, 14),
            datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
        )
        provider = _provider(cache)

        result = await provider._async_get_team_schedule()

    assert result is cache
    provider.async_call_espn_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_match_day_cache_is_reused_within_normal_refresh_interval():
    with freeze_time("2026-09-13T18:05:00Z"):
        cache = _cache(
            date(2026, 9, 13),
            datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc),
        )
        provider = _provider(cache)

        result = await provider._async_get_team_schedule()

    assert result is cache
    provider.async_call_espn_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_match_day_cache_refreshes_after_normal_refresh_interval():
    with freeze_time("2026-09-13T18:11:00Z"):
        cache = _cache(
            date(2026, 9, 13),
            datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc),
        )
        provider = _provider(cache)
        provider.async_call_espn_api = AsyncMock(
            side_effect=[
                {
                    "data": {"team": {"nextEvent": []}},
                    "url": "team-info",
                    "timestamp": "2026-09-13T18:11:00+00:00",
                },
                {
                    "data": {"events": [_completed_event()]},
                    "url": "team-schedule",
                    "timestamp": "2026-09-13T18:11:00+00:00",
                },
            ]
        )

        result = await provider._async_get_team_schedule()

    assert provider.async_call_espn_api.await_count == 2
    assert result["expires"] == date(2026, 9, 13)
    assert result["cached_at"] == datetime(
        2026, 9, 13, 18, 11, tzinfo=timezone.utc
    )
    assert result["derived_league_name"] == "Greek Super League"


@pytest.mark.asyncio
async def test_old_match_day_cache_without_timestamp_is_refreshed_once():
    """Existing in-memory cache entries from older code must not stay stale."""
    with freeze_time("2026-09-13T18:11:00Z"):
        cache = _cache(date(2026, 9, 13), None)
        provider = _provider(cache)
        provider.async_call_espn_api = AsyncMock(
            side_effect=[
                {
                    "data": {"team": {"nextEvent": []}},
                    "url": "team-info",
                    "timestamp": "2026-09-13T18:11:00+00:00",
                },
                {
                    "data": {"events": [_completed_event()]},
                    "url": "team-schedule",
                    "timestamp": "2026-09-13T18:11:00+00:00",
                },
            ]
        )

        result = await provider._async_get_team_schedule()

    assert provider.async_call_espn_api.await_count == 2
    assert result["cached_at"] == datetime(
        2026, 9, 13, 18, 11, tzinfo=timezone.utc
    )


def _local_date(offset_hours: int):
    """A ``date`` whose ``today()`` is HA's local date: the (frozen) UTC clock
    shifted by the local UTC offset, independent of the true UTC time."""

    class LocalDate(date):
        @classmethod
        def today(cls):
            return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).date()

    return LocalDate


def _live_match_event() -> dict:
    return {
        "id": "sea-col",
        "date": "2026-09-20T01:30Z",
        "season": {"displayName": "2026 MLS"},
        "competitions": [{"status": {"type": {"state": "in"}}}],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("utc_offset_hours", [-7, 0, 9])
async def test_evening_kickoff_cache_refreshes_when_local_date_lags_utc(utc_offset_hours):
    """A 01:30Z kickoff is 6:30 PM the previous day in Pacific time. The cache
    expires on the event's UTC date (2026-09-20), so freshness must be judged
    against the UTC date, not HA's local date: with a local date of 9/19 the
    pre-kickoff nextEvent snapshot was reused for the whole match and the
    sensor stayed PRE."""
    with freeze_time("2026-09-20T01:50:00Z"), patch(
        "custom_components.teamtracker.provide_espn_all.date",
        _local_date(utc_offset_hours),
    ):
        cache = _cache(
            date(2026, 9, 20),
            datetime(2026, 9, 19, 15, 41, tzinfo=timezone.utc),
        )
        provider = _provider(cache)
        provider.async_call_espn_api = AsyncMock(
            side_effect=[
                {
                    "data": {"team": {"nextEvent": [_live_match_event()]}},
                    "url": "team-info",
                    "timestamp": "2026-09-20T01:50:00+00:00",
                },
                {
                    "data": {"events": []},
                    "url": "team-schedule",
                    "timestamp": "2026-09-20T01:50:00+00:00",
                },
            ]
        )

        result = await provider._async_get_team_schedule()

    assert provider.async_call_espn_api.await_count == 2
    state = result["next_events"][0]["competitions"][0]["status"]["type"]["state"]
    assert state == "in"


@pytest.mark.asyncio
async def test_evening_cache_still_reused_before_the_utc_match_day():
    """The fix must not add refreshes: a day before the match's UTC date the
    cache is still reused, whatever the local timezone."""
    with freeze_time("2026-09-19T20:00:00Z"), patch(
        "custom_components.teamtracker.provide_espn_all.date", _local_date(-7)
    ):
        cache = _cache(
            date(2026, 9, 20),
            datetime(2026, 9, 19, 15, 41, tzinfo=timezone.utc),
        )
        provider = _provider(cache)

        result = await provider._async_get_team_schedule()

    assert result is cache
    provider.async_call_espn_api.assert_not_awaited()
