"""Integration tests for multiscrape __init__.py setup."""

from datetime import timedelta

import pytest
from homeassistant.const import (CONF_NAME, CONF_RESOURCE, CONF_SCAN_INTERVAL,
                                 SERVICE_RELOAD, Platform)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.multiscrape import (_async_process_config,
                                           _async_setup_shared_data,
                                           async_get_config_and_coordinator,
                                           async_setup)
from custom_components.multiscrape.const import (COORDINATOR, DOMAIN,
                                                 PLATFORM_IDX, SCRAPER,
                                                 SCRAPER_DATA, SCRAPER_IDX)


@pytest.fixture
def minimal_config():
    """Create minimal valid configuration."""
    return {
        DOMAIN: [
            {
                CONF_NAME: "test_scraper",
                CONF_RESOURCE: "https://example.com",
                CONF_SCAN_INTERVAL: timedelta(seconds=60),
                Platform.SENSOR: [
                    {
                        CONF_NAME: "test_sensor",
                        "select": ".value",
                    }
                ],
            }
        ]
    }


@pytest.fixture
def empty_config():
    """Create configuration with no resource (service-only mode)."""
    return {DOMAIN: [{}]}


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_setup_shared_data(hass: HomeAssistant):
    """Test _async_setup_shared_data creates required data structures."""
    # Act
    _async_setup_shared_data(hass)

    # Assert
    assert DOMAIN in hass.data
    assert SCRAPER_DATA in hass.data[DOMAIN]
    assert Platform.SENSOR in hass.data[DOMAIN]
    assert Platform.BINARY_SENSOR in hass.data[DOMAIN]
    assert Platform.BUTTON in hass.data[DOMAIN]
    assert isinstance(hass.data[DOMAIN][SCRAPER_DATA], list)
    assert isinstance(hass.data[DOMAIN][Platform.SENSOR], list)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_setup_registers_reload_service(hass: HomeAssistant, empty_config):
    """Test async_setup registers the reload service."""
    # Act
    await async_setup(hass, empty_config)

    # Assert
    assert hass.services.has_service(DOMAIN, SERVICE_RELOAD)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_setup_registers_integration_services(
    hass: HomeAssistant, empty_config
):
    """Test async_setup registers integration-level services."""
    # Act
    await async_setup(hass, empty_config)

    # Assert - get_content and scrape services should be registered
    assert hass.services.has_service(DOMAIN, "get_content")
    assert hass.services.has_service(DOMAIN, "scrape")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_setup_service_only_mode(hass: HomeAssistant, empty_config):
    """Test async_setup works in service-only mode (no resource configured)."""
    # Act
    result = await async_setup(hass, empty_config)

    # Assert
    assert result is True
    # Should have set up services but not processed any scrapers
    assert hass.services.has_service(DOMAIN, "get_content")
    assert hass.services.has_service(DOMAIN, "scrape")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_creates_scraper_data(
    hass: HomeAssistant, minimal_config
):
    """Test _async_process_config creates scraper data structures."""
    # Arrange
    _async_setup_shared_data(hass)

    # Act
    result = await _async_process_config(hass, minimal_config)

    # Assert
    assert result is True
    assert len(hass.data[DOMAIN][SCRAPER_DATA]) == 1
    scraper_data = hass.data[DOMAIN][SCRAPER_DATA][0]
    assert SCRAPER in scraper_data
    assert COORDINATOR in scraper_data


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_generates_name_for_unnamed_scraper(
    hass: HomeAssistant
):
    """Test _async_process_config generates name when CONF_NAME is missing."""
    # Arrange
    _async_setup_shared_data(hass)
    config_without_name = {
        DOMAIN: [
            {
                CONF_RESOURCE: "https://example.com",
                Platform.SENSOR: [
                    {
                        CONF_NAME: "test_sensor",
                        "select": ".value",
                    }
                ],
            }
        ]
    }

    # Act
    result = await _async_process_config(hass, config_without_name)

    # Assert
    assert result is True
    # Should have generated a name like "Scraper_noname_0"
    assert len(hass.data[DOMAIN][SCRAPER_DATA]) == 1


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_creates_config_services(
    hass: HomeAssistant, minimal_config
):
    """Test _async_process_config creates per-config services."""
    # Arrange
    _async_setup_shared_data(hass)

    # Act
    await _async_process_config(hass, minimal_config)

    # Assert - trigger service should be registered
    assert hass.services.has_service(DOMAIN, "trigger_test_scraper")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_stores_platform_configs(
    hass: HomeAssistant, minimal_config
):
    """Test _async_process_config stores platform configurations."""
    # Arrange
    _async_setup_shared_data(hass)

    # Act
    await _async_process_config(hass, minimal_config)

    # Assert
    assert len(hass.data[DOMAIN][Platform.SENSOR]) == 1
    sensor_config = hass.data[DOMAIN][Platform.SENSOR][0]
    assert sensor_config[CONF_NAME] == "test_sensor"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_with_multiple_platforms(hass: HomeAssistant):
    """Test _async_process_config handles multiple platforms."""
    # Arrange
    _async_setup_shared_data(hass)
    config = {
        DOMAIN: [
            {
                CONF_NAME: "multi_platform_scraper",
                CONF_RESOURCE: "https://example.com",
                Platform.SENSOR: [
                    {
                        CONF_NAME: "sensor1",
                        "select": ".value1",
                    }
                ],
                Platform.BINARY_SENSOR: [
                    {
                        CONF_NAME: "binary1",
                        "select": ".status",
                    }
                ],
                Platform.BUTTON: [
                    {
                        CONF_NAME: "button1",
                    }
                ],
            }
        ]
    }

    # Act
    await _async_process_config(hass, config)

    # Assert
    assert len(hass.data[DOMAIN][Platform.SENSOR]) == 1
    assert len(hass.data[DOMAIN][Platform.BINARY_SENSOR]) == 1
    assert len(hass.data[DOMAIN][Platform.BUTTON]) == 1


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_with_multiple_sensors_per_scraper(
    hass: HomeAssistant,
):
    """Test _async_process_config handles multiple sensors in one scraper."""
    # Arrange
    _async_setup_shared_data(hass)
    config = {
        DOMAIN: [
            {
                CONF_NAME: "multi_sensor_scraper",
                CONF_RESOURCE: "https://example.com",
                Platform.SENSOR: [
                    {CONF_NAME: "sensor1", "select": ".value1"},
                    {CONF_NAME: "sensor2", "select": ".value2"},
                    {CONF_NAME: "sensor3", "select": ".value3"},
                ],
            }
        ]
    }

    # Act
    await _async_process_config(hass, config)

    # Assert
    assert len(hass.data[DOMAIN][Platform.SENSOR]) == 3
    assert len(hass.data[DOMAIN][SCRAPER_DATA]) == 1  # Only one scraper


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_with_multiple_scrapers(hass: HomeAssistant):
    """Test _async_process_config handles multiple scraper configurations."""
    # Arrange
    _async_setup_shared_data(hass)
    config = {
        DOMAIN: [
            {
                CONF_NAME: "scraper1",
                CONF_RESOURCE: "https://example.com/1",
                Platform.SENSOR: [{CONF_NAME: "sensor1", "select": ".value"}],
            },
            {
                CONF_NAME: "scraper2",
                CONF_RESOURCE: "https://example.com/2",
                Platform.SENSOR: [{CONF_NAME: "sensor2", "select": ".value"}],
            },
        ]
    }

    # Act
    await _async_process_config(hass, config)

    # Assert
    assert len(hass.data[DOMAIN][SCRAPER_DATA]) == 2
    assert len(hass.data[DOMAIN][Platform.SENSOR]) == 2
    # Each scraper should have its own trigger service
    assert hass.services.has_service(DOMAIN, "trigger_scraper1")
    assert hass.services.has_service(DOMAIN, "trigger_scraper2")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_get_config_and_coordinator(hass: HomeAssistant, minimal_config):
    """Test async_get_config_and_coordinator retrieves correct data."""
    # Arrange
    _async_setup_shared_data(hass)
    await _async_process_config(hass, minimal_config)

    discovery_info = {SCRAPER_IDX: 0, PLATFORM_IDX: 0}

    # Act
    conf, coordinator, scraper = await async_get_config_and_coordinator(
        hass, Platform.SENSOR, discovery_info
    )

    # Assert
    assert conf[CONF_NAME] == "test_sensor"
    assert coordinator is not None
    assert scraper is not None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_with_form_submit(hass: HomeAssistant):
    """Test _async_process_config handles form submission configuration."""
    # Arrange
    _async_setup_shared_data(hass)
    config = {
        DOMAIN: [
            {
                CONF_NAME: "form_scraper",
                CONF_RESOURCE: "https://example.com/data",
                "form_submit": {
                    CONF_RESOURCE: "https://example.com/login",
                    "select": "form",
                    "input": {"username": "user", "password": "pass"},
                    "variables": [],  # Form variables (can be empty list)
                },
                Platform.SENSOR: [
                    {
                        CONF_NAME: "sensor1",
                        "select": ".value",
                    }
                ],
            }
        ]
    }

    # Act
    result = await _async_process_config(hass, config)

    # Assert
    assert result is True
    assert len(hass.data[DOMAIN][SCRAPER_DATA]) == 1


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_with_resource_template(hass: HomeAssistant):
    """Test _async_process_config handles resource_template."""
    # Arrange
    _async_setup_shared_data(hass)
    config = {
        DOMAIN: [
            {
                CONF_NAME: "template_scraper",
                "resource_template": Template(
                    "https://example.com/{{ states('sensor.id') }}", hass
                ),
                Platform.SENSOR: [
                    {
                        CONF_NAME: "sensor1",
                        "select": ".value",
                    }
                ],
            }
        ]
    }

    # Act
    result = await _async_process_config(hass, config)

    # Assert
    assert result is True
    assert len(hass.data[DOMAIN][SCRAPER_DATA]) == 1


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.respx
async def test_async_process_config_skips_platforms_not_in_config(hass: HomeAssistant):
    """Test _async_process_config only processes platforms that are configured."""
    # Arrange
    _async_setup_shared_data(hass)
    config = {
        DOMAIN: [
            {
                CONF_NAME: "sensor_only_scraper",
                CONF_RESOURCE: "https://example.com",
                Platform.SENSOR: [
                    {
                        CONF_NAME: "sensor1",
                        "select": ".value",
                    }
                ],
                # No binary_sensor or button configured
            }
        ]
    }

    # Act
    await _async_process_config(hass, config)

    # Assert
    assert len(hass.data[DOMAIN][Platform.SENSOR]) == 1
    assert len(hass.data[DOMAIN][Platform.BINARY_SENSOR]) == 0
    assert len(hass.data[DOMAIN][Platform.BUTTON]) == 0
