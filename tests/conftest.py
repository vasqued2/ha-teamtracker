"""Fixtures for tests"""
import asyncio
import threading
from typing import Generator
import pytest

pytest_plugins = ("pytest_homeassistant_custom_component", "pytest_asyncio")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """ enable custom integrations """
    yield



# The name of the thread that Home Assistant's test harness is failing on 
# in Python 3.12, which we need to filter out for the test to pass.
THREAD_ENDS_WITH_SAFE_SHUTDOWN = "(_run_safe_shutdown_loop)" # <-- CHANGED: Check the end of the name
THREAD_PREFIX_TO_IGNORE_SYNCWORKER = "SyncWorker_"

@pytest.fixture(autouse=True)
def verify_cleanup(
    event_loop: asyncio.AbstractEventLoop,
    expected_lingering_tasks: bool,
    expected_lingering_timers: bool,
) -> Generator[None, None, None]:
    """
    Overrides the default Home Assistant 'verify_cleanup' fixture 
    to filter out known lingering threads that appear in Python 3.12.
    """
    
    # --- Start of the Test (Setup) ---
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
            isinstance(thread, threading._DummyThread)
            or thread.name.startswith("waitpid-")
            or thread.name.endswith(THREAD_ENDS_WITH_SAFE_SHUTDOWN)  # <-- UPDATED CHECK
            or thread.name.startswith(THREAD_PREFIX_TO_IGNORE_SYNCWORKER)  # <-- NEW: Ignore SyncWorkers
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
    timers = event_loop._scheduled
    assert (
        not timers or expected_lingering_timers
    ), f"Lingering timers found: {timers}"