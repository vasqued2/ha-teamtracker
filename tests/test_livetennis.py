""" Test TeamTracker Live Tennis API provider """
from datetime import timedelta
import json
import logging
import os
from unittest.mock import AsyncMock, patch

import arrow
from freezegun import freeze_time
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from yarl import URL

from custom_components.teamtracker.const import COORDINATOR, DOMAIN
from custom_components.teamtracker.provide_espn import EspnProvider
from custom_components.teamtracker.provide_livetennis import (
    LIVETENNIS_API_KEY_ENV,
    LIVETENNIS_BASE_URL,
    LT_STATUS_COMPLETED,
    LT_STATUS_LIVE,
    LiveTennisProvider,
)
from custom_components.teamtracker.provider_factory import get_provider
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from tests.conftest import LIVETENNIS_TEST_KEY

_LOGGER = logging.getLogger(__name__)

LIVETENNIS_DATA = [
    {
        "league_id": "LTATP",
        "team_id": "DJOKOVIC",
        "name": "test_pre",
        "sport_path": "livetennis",
        "league_path": "atp",
        "timeout": 120,
    },
    {
        "league_id": "LTATP",
        "team_id": "SINNER",
        "name": "test_in",
        "sport_path": "livetennis",
        "league_path": "atp",
        "timeout": 120,
    },
    {
        "league_id": "LTATP",
        "team_id": "RYBAKINA",
        "name": "test_in_tiebreak",
        "sport_path": "livetennis",
        "league_path": "atp",
        "timeout": 120,
    },
    {
        "league_id": "LTATP",
        "team_id": "SWIATEK",
        "name": "test_post",
        "sport_path": "livetennis",
        "league_path": "atp",
        "timeout": 120,
    },
    {
        # Retired, and the feed carries an empty games array for it
        "league_id": "LTATP",
        "team_id": "FRITZ",
        "name": "test_post_retired",
        "sport_path": "livetennis",
        "league_path": "atp",
        "timeout": 120,
    },
    {
        # Every listing fails, so the sensor reports an API error
        "league_id": "LTATP",
        "team_id": "SINNER",
        "name": "api_error_atp",
        "sport_path": "livetennis",
        "league_path": "atp",
        "timeout": 120,
    },
    {
        # Not a tour this API serves; refused before any call is made
        "league_id": "XXX",
        "team_id": "SINNER",
        "name": "test_invalid_tour",
        "sport_path": "livetennis",
        "league_path": "INVALID_LEAGUE_PATH",
        "timeout": 120,
    },
    {
        # Valid tour, but the player is not in any listing
        "league_id": "LTATP",
        "team_id": "INVALID_TEAM_ID",
        "name": "test_invalid_team",
        "sport_path": "livetennis",
        "league_path": "atp",
        "timeout": 120,
    },
]


@freeze_time("2026-09-12 14:00:00")
@pytest.mark.parametrize("lt", LIVETENNIS_DATA, ids=lambda x: x["name"])
async def test_livetennis(hass, snapshot, mock_call_livetennis_api, mocker, lt):
    """
        This regression tests attributes for the Live Tennis API
            It runs a test for state PRE, IN, and POST
            To set a new snapshot baseline: pytest --snapshot-update
    """

    SAMPLE_DATA = lt

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sample",
        data=SAMPLE_DATA,
    )

    mocker.patch("locale.getlocale", return_value=("en", 0))

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "teamtracker" in hass.config.components

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

#
# Validate sensor state and attributes
#

    sensor_state = hass.states.get(f"sensor.{lt['name']}")
    assert sensor_state is not None

    attributes = dict(sensor_state.attributes)

    #  The key is sent as a header and must never reach a URL or an attribute
    assert LIVETENNIS_TEST_KEY not in json.dumps(attributes)

    attributes.pop("kickoff_in", None)
    attributes.pop("last_update", None)

    assert attributes == snapshot


async def test_livetennis_not_selected_without_api_key(hass):
    """With no key configured the provider is never selected.

    The integration must behave exactly as it did before this provider
    existed, so the factory falls through to its default.
    """

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(LIVETENNIS_API_KEY_ENV, None)

        provider = get_provider("livetennis", "atp", "SINNER", None)

    assert isinstance(provider, EspnProvider)
    assert not isinstance(provider, LiveTennisProvider)


async def test_livetennis_selected_with_api_key(hass):
    """With a key configured the provider is selected and polls conservatively."""

    with patch.dict(os.environ, {LIVETENNIS_API_KEY_ENV: LIVETENNIS_TEST_KEY}):
        provider = get_provider("livetennis", "atp", "SINNER", None)

    assert isinstance(provider, LiveTennisProvider)
    assert provider.ATTRIBUTION == "Powered by livetennisapi.com"

    #
    #  The free tier allows 100 requests/day. 15 minutes is 96 of them, so the
    #  in-play rate must not be faster than the default.
    #
    assert provider.DEFAULT_REFRESH_RATE == timedelta(minutes=15)
    assert provider.RAPID_REFRESH_RATE >= provider.DEFAULT_REFRESH_RATE


@freeze_time("2026-09-12 14:00:00")
async def test_livetennis_completed_listing_probed_once(hass, mocker):
    """A FREE key is refused status=completed; the call is not spent again.

    status=completed is part of the paid history product and answers
    403 upgrade_required on a free key. The provider must learn that once
    rather than on every refresh.
    """

    calls = []

    async def _mock_api(hass_arg, base_url, params, sensor_name, league_id):
        status = params.get("status")
        calls.append(status)
        url = str(URL(base_url).with_query(params))
        timestamp = arrow.now().format(arrow.FORMAT_W3C)

        if status == LT_STATUS_COMPLETED:
            return {
                "lt_data": None,
                "url": url,
                "timestamp": timestamp,
                "status": 403,
            }

        with open(f"tests/tt/livetennis-{status}.json", "r") as f:
            return {
                "lt_data": json.load(f),
                "url": url,
                "timestamp": timestamp,
                "status": 200,
            }

    mocker.patch("locale.getlocale", return_value=("en", 0))

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sample",
        data={
            "league_id": "LTATP",
            "team_id": "SINNER",
            "name": "test_free_tier",
            "sport_path": "livetennis",
            "league_path": "atp",
            "timeout": 120,
        },
    )

    with patch.dict(os.environ, {LIVETENNIS_API_KEY_ENV: LIVETENNIS_TEST_KEY}), patch(
        "custom_components.teamtracker.provide_livetennis.LiveTennisProvider.async_call_livetennis_api",
        new_callable=AsyncMock,
    ) as mock_livetennis:
        mock_livetennis.side_effect = _mock_api

        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert calls.count(LT_STATUS_LIVE) == 1
        assert calls.count(LT_STATUS_COMPLETED) == 1

        #  The sensor still reports the live match the free tier does serve
        sensor_state = hass.states.get("sensor.test_free_tier")
        assert sensor_state is not None
        assert sensor_state.state == "IN"

        #
        #  Drop the per-refresh scoreboard cache so the next refresh really
        #  re-reads the API, then confirm only the live listing is asked for.
        #
        hass.data[DOMAIN]["data_cache"].pop("scoreboard_data", None)

        coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert calls.count(LT_STATUS_LIVE) == 2
    assert calls.count(LT_STATUS_COMPLETED) == 1


async def test_livetennis_api_call_sends_key_as_header_never_in_url(
    hass, aioclient_mock
):
    """The API key travels in a header, so it cannot leak into a URL or a log.

    api_url is published as a sensor attribute, so this is the one place the
    key must never appear.
    """

    params = {"status": LT_STATUS_LIVE, "tour": "atp", "limit": 200}
    expected_url = str(URL(LIVETENNIS_BASE_URL).with_query(params))
    payload = {"data": [], "meta": {"count": 0}}

    aioclient_mock.get(expected_url, json=payload)

    provider = LiveTennisProvider(None)

    with patch.dict(os.environ, {LIVETENNIS_API_KEY_ENV: LIVETENNIS_TEST_KEY}):
        response = await provider.async_call_livetennis_api(
            hass, LIVETENNIS_BASE_URL, params, "test_headers", "atp"
        )

    assert response["status"] == 200
    assert response["lt_data"] == payload

    #  Never in the URL that is published as the api_url attribute
    assert LIVETENNIS_TEST_KEY not in response["url"]

    #  ...but it was sent
    assert len(aioclient_mock.mock_calls) == 1
    sent_headers = aioclient_mock.mock_calls[0][3]
    assert sent_headers["X-API-Key"] == LIVETENNIS_TEST_KEY


async def test_livetennis_api_call_reports_upgrade_required(hass, aioclient_mock):
    """A tier-gated listing answers 403, which the caller must be able to see."""

    params = {"status": LT_STATUS_COMPLETED, "tour": "atp", "limit": 200}
    expected_url = str(URL(LIVETENNIS_BASE_URL).with_query(params))

    aioclient_mock.get(expected_url, status=403, json={"error": "upgrade_required"})

    provider = LiveTennisProvider(None)

    with patch.dict(os.environ, {LIVETENNIS_API_KEY_ENV: LIVETENNIS_TEST_KEY}):
        response = await provider.async_call_livetennis_api(
            hass, LIVETENNIS_BASE_URL, params, "test_403", "atp"
        )

    assert response["status"] == 403
    assert response["lt_data"] is None
