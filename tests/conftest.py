"""Fixtures for tests"""
import asyncio
import pytest

pytest_plugins = ("pytest_homeassistant_custom_component", "pytest_asyncio")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
