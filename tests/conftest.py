"""Global fixtures for Multiscrape integration."""

# Fixtures allow you to replace functions with a Mock object. You can perform
# many options via the Mock to reflect a particular behavior from the original
# function that you want to see without going through the function's actual logic.
# Fixtures can either be passed into tests as parameters, or if autouse=True, they
# will automatically be used across all tests.
#
# Fixtures that are defined in conftest.py are available across all tests. You can also
# define fixtures within a particular test file to scope them locally.
#
# pytest_homeassistant_custom_component provides some fixtures that are provided by
# Home Assistant core. You can find those fixture definitions here:
# https://github.com/MatthewFlamm/pytest-homeassistant-custom-component/blob/master/pytest_homeassistant_custom_component/common.py
#
# See here for more info: https://docs.pytest.org/en/latest/fixture.html (note that
# pytest includes fixtures OOB which you can use as defined on this page)
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from homeassistant.core import HomeAssistant

from custom_components.multiscrape.const import DEFAULT_SEPARATOR
from custom_components.multiscrape.coordinator import (
    ContentRequestManager, MultiscrapeDataUpdateCoordinator)
from custom_components.multiscrape.scraper import Scraper

# from custom_components.multiscrape.const import (CONF_CONFIG_NAME,
#                                                CONF_METER_TYPE, DOMAIN)

pytest_plugins = "pytest_homeassistant_custom_component"


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    yield


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


# ============================================================================
# Phase 1: Proper Async Fixtures
# ============================================================================


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response object."""
    class MockResponse:
        def __init__(self, text="", status_code=200, headers=None, cookies=None):
            self.text = text
            self.status_code = status_code
            self.headers = headers or {}
            self.cookies = cookies or {}

        def raise_for_status(self):
            if 400 <= self.status_code <= 599:
                raise Exception(f"HTTP {self.status_code}")

    return MockResponse


@pytest.fixture
async def http_wrapper(hass):
    """Create a real HttpWrapper instance for testing (requires respx mocking)."""
    from homeassistant.helpers.httpx_client import get_async_client

    from custom_components.multiscrape.http import HttpWrapper
    from custom_components.multiscrape.util import (create_dict_renderer,
                                                    create_renderer)

    client = get_async_client(hass, verify_ssl=True)
    wrapper = HttpWrapper(
        config_name="test_wrapper",
        hass=hass,
        client=client,
        file_manager=None,
        timeout=10,
        params_renderer=create_dict_renderer(hass, None),
        headers_renderer=create_dict_renderer(hass, None),
        data_renderer=create_renderer(hass, None),
    )
    return wrapper


@pytest.fixture
def mock_http_wrapper(mock_http_response):
    """Create a mock HttpWrapper with proper async behavior."""
    mock = AsyncMock()
    mock.async_request = AsyncMock(return_value=mock_http_response(
        text='<div class="test">Test Content</div>'
    ))
    return mock


@pytest.fixture
async def scraper(hass: HomeAssistant):
    """Create a Scraper instance for testing."""
    return Scraper(
        config_name="test_scraper",
        hass=hass,
        file_manager=None,
        parser="lxml",
        separator=DEFAULT_SEPARATOR,
    )


@pytest.fixture
def mock_file_manager():
    """Create a mock file manager."""
    mock = MagicMock()
    mock.write = MagicMock()
    mock.empty_folder = MagicMock()
    return mock


@pytest.fixture
def mock_form_submitter():
    """Create a mock form submitter."""
    mock = AsyncMock()
    mock.should_submit = False
    mock.async_submit = AsyncMock(return_value=(None, None))
    mock.scrape_variables = MagicMock(return_value={})
    mock.notify_scrape_exception = MagicMock()
    return mock


@pytest.fixture
def mock_resource_renderer():
    """Create a mock resource renderer."""
    return lambda: "https://example.com"


@pytest.fixture
def content_request_manager(
    mock_http_wrapper, mock_resource_renderer, mock_form_submitter
):
    """Create a ContentRequestManager for testing."""
    return ContentRequestManager(
        config_name="test_request_manager",
        http=mock_http_wrapper,
        resource_renderer=mock_resource_renderer,
        form=mock_form_submitter,
    )


@pytest.fixture
async def coordinator(
    hass: HomeAssistant,
    content_request_manager,
    mock_file_manager,
    scraper,
):
    """Create a MultiscrapeDataUpdateCoordinator for testing."""
    from datetime import timedelta

    coordinator = MultiscrapeDataUpdateCoordinator(
        config_name="test_coordinator",
        hass=hass,
        request_manager=content_request_manager,
        file_manager=mock_file_manager,
        scraper=scraper,
        update_interval=timedelta(seconds=60),
    )
    return coordinator


@pytest.fixture
def respx_mock():
    """Provide a respx mock for HTTP testing."""
    with respx.mock:
        yield respx

