"""Fixtures for tests"""
import asyncio
import threading
from collections.abc import Generator # <-- New import
import pytest
import logging
import json
import aiofiles
from unittest.mock import AsyncMock, patch

_LOGGER = logging.getLogger(__name__)

pytest_plugins = ("pytest_homeassistant_custom_component", "pytest_asyncio")


@pytest.fixture
async def mock_espn_api(hass):
    """Global fixture to mock the ESPN API and return local JSON data."""
    
    # Path to your test data
    DATA_PATH = "tests/tt/"

    async def _get_mock_data(hass, sensor_name, team_id, url, file_override=False):
        """Helper to load local files based on URL logic."""

        clean_url = url.split('?')[0]

        if "schedule" in clean_url:
            file_name = "schedule.json"
        elif "teams" in clean_url:
            if clean_url[-1].isdigit(): # if there is any team identifier, use team 194
                file_name = "teams-194.json"
            elif "football" in clean_url:
                file_name = "teams-college-football.json"
            else:
                file_name = "teams.json"
        elif "/all/" in clean_url:
            file_name = "scoreboard_all_leagues.json"
        else:
            file_name = "all.json"

#        return None

        try:
            with open(f"{DATA_PATH}{file_name}", "r") as f:
                data = json.load(f)
                return data
        except FileNotFoundError:
            return None

    # Patch the actual utility function
    with patch("custom_components.teamtracker.config_flow.async_call_espn_api2", new_callable=AsyncMock) as mock:        # Define the side effect to mimic your original file-override logic
#        mock.side_effect = lambda hass, name, tid, url, override=False: _get_mock_data(url)
        mock.side_effect = _get_mock_data
        yield mock



@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """ enable custom integrations """
    yield

#
# Ignore the specified lingering threads (Compatible w/ Python 3.12 and earlier only)
#

THREAD_ENDS_WITH_SAFE_SHUTDOWN = "(_run_safe_shutdown_loop)" # <-- CHANGED: Check the end of the name
THREAD_PREFIX_TO_IGNORE_SYNCWORKER = "SyncWorker_"

@pytest.fixture(autouse=False)
def verify_cleanup(
#    event_loop: asyncio.AbstractEventLoop,
    expected_lingering_tasks: bool,
    expected_lingering_timers: bool,
) -> Generator[None]:
    '''
    Overrides the default Home Assistant 'verify_cleanup' fixture 
    to filter out known lingering threads that appear in Python 3.12.
    '''
    # --- Start of the Test (Setup) ---
    event_loop = asyncio.get_event_loop()
    threads_before = frozenset(threading.enumerate())
    tasks_before = asyncio.all_tasks(event_loop)

    
    # The test runs here
    yield
    
    # --- End of the Test (Teardown Verification) ---

    # 1. Thread Cleanup Check
    threads_after = frozenset(threading.enumerate())
    lingering_threads = threads_after - threads_before
    
    # Filter out safe threads (dummy/waitpid) and the specific ignored thread
    lingering_threads = {
        thread
        for thread in lingering_threads
        if not (
            isinstance(thread, threading._DummyThread) # pylint: disable=protected-access
            or thread.name.startswith("waitpid-")
            or thread.name.endswith(THREAD_ENDS_WITH_SAFE_SHUTDOWN)
            or thread.name.startswith(THREAD_PREFIX_TO_IGNORE_SYNCWORKER)
        )
    }

    assert not lingering_threads, (
        "Lingering threads found: "
        f"{[thread.name for thread in lingering_threads]}"
    )

    # 2. Asynchronous Task Cleanup Check (Kept from HA fixture)
    tasks_after = asyncio.all_tasks(event_loop)
    lingering_tasks = tasks_after - tasks_before
    assert (
        not lingering_tasks or expected_lingering_tasks
    ), f"Lingering tasks found: {lingering_tasks}"

    # 3. Timer Cleanup Check (Kept from HA fixture)
    try:
        timers = event_loop._scheduled # pylint: disable=protected-access
    except AttributeError:
        # Python 3.13+ - use different approach or skip timer check
        # In Python 3.13, _scheduled was refactored
        timers = []
        _LOGGER.debug("Timer check skipped on Python 3.13+")

    assert (
        not timers or expected_lingering_timers
    ), f"Lingering timers found: {timers}"
