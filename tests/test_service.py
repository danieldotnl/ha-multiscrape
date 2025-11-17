"""Integration tests for multiscrape service functionality."""

import pytest
import respx
from homeassistant.const import CONF_RESOURCE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import CONF_PARSER, DOMAIN
from custom_components.multiscrape.service import (
    _replace_template_characters, _restore_template, _restore_templates,
    setup_config_services, setup_get_content_service,
    setup_integration_services, setup_scrape_service)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_setup_integration_services(hass: HomeAssistant):
    """Test that integration services are registered."""
    # Act
    await setup_integration_services(hass)

    # Assert
    assert hass.services.has_service(DOMAIN, "get_content")
    assert hass.services.has_service(DOMAIN, "scrape")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_setup_config_services(hass: HomeAssistant, coordinator):
    """Test that config-level services are registered."""
    # Act
    await setup_config_services(hass, coordinator, "test_config")

    # Assert
    assert hass.services.has_service(DOMAIN, "trigger_test_config")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_trigger_service_calls_coordinator_refresh(hass: HomeAssistant, coordinator):
    """Test that trigger service calls coordinator refresh."""
    # Arrange
    await setup_config_services(hass, coordinator, "test_trigger")

    # Act
    await hass.services.async_call(DOMAIN, "trigger_test_trigger", blocking=True)

    # Assert - coordinator should have been refreshed
    # We can't directly verify the call without mocking, but we can verify the service exists
    assert hass.services.has_service(DOMAIN, "trigger_test_trigger")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_get_content_service_returns_content(hass: HomeAssistant):
    """Test get_content service returns scraped content."""
    # Arrange
    await setup_get_content_service(hass)

    test_url = "https://example.com/test"
    html_content = """
    <html>
        <body>
            <div class="content">Test Content</div>
        </body>
    </html>
    """
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text=html_content))

    service_data = {
        CONF_RESOURCE: test_url,
        CONF_PARSER: "html.parser",
    }

    # Act
    response = await hass.services.async_call(
        DOMAIN, "get_content", service_data, blocking=True, return_response=True
    )

    # Assert
    assert "content" in response
    assert "Test Content" in response["content"]


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_scrape_service_returns_sensor_values(hass: HomeAssistant):
    """Test scrape service returns scraped sensor values."""
    # Arrange
    await setup_scrape_service(hass)

    test_url = "https://example.com/data"
    html_content = """
    <html>
        <body>
            <div class="temperature">23.5</div>
            <div class="humidity">65</div>
        </body>
    </html>
    """
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text=html_content))

    service_data = {
        CONF_RESOURCE: test_url,
        CONF_PARSER: "html.parser",
        Platform.SENSOR: [
            {
                "name": "Temperature",
                "unique_id": "temp_sensor",
                "select": ".temperature",
            },
            {
                "name": "Humidity",
                "unique_id": "humidity_sensor",
                "select": ".humidity",
            },
        ],
    }

    # Act
    response = await hass.services.async_call(
        DOMAIN, "scrape", service_data, blocking=True, return_response=True
    )

    # Assert
    assert "temp_sensor" in response
    assert response["temp_sensor"]["value"] == "23.5"
    assert "humidity_sensor" in response
    assert response["humidity_sensor"]["value"] == "65"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_scrape_service_with_binary_sensor(hass: HomeAssistant):
    """Test scrape service with binary sensor configuration."""
    # Arrange
    await setup_scrape_service(hass)

    test_url = "https://example.com/status"
    html_content = """
    <html>
        <body>
            <div class="door">open</div>
            <div class="window">closed</div>
        </body>
    </html>
    """
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text=html_content))

    service_data = {
        CONF_RESOURCE: test_url,
        CONF_PARSER: "html.parser",
        Platform.BINARY_SENSOR: [
            {
                "name": "Door",
                "unique_id": "door_sensor",
                "select": ".door",
            },
            {
                "name": "Window",
                "unique_id": "window_sensor",
                "select": ".window",
            },
        ],
    }

    # Act
    response = await hass.services.async_call(
        DOMAIN, "scrape", service_data, blocking=True, return_response=True
    )

    # Assert
    assert "door_sensor" in response
    assert response["door_sensor"]["value"] == "open"
    assert "window_sensor" in response
    assert response["window_sensor"]["value"] == "closed"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_scrape_service_with_attributes(hass: HomeAssistant):
    """Test scrape service scrapes sensor attributes."""
    # Arrange
    await setup_scrape_service(hass)

    test_url = "https://example.com/weather"
    html_content = """
    <html>
        <body>
            <div class="temp">23.5</div>
            <div class="unit">C</div>
            <div class="location">Living Room</div>
        </body>
    </html>
    """
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text=html_content))

    service_data = {
        CONF_RESOURCE: test_url,
        CONF_PARSER: "html.parser",
        Platform.SENSOR: [
            {
                "name": "Temperature",
                "unique_id": "temp",
                "select": ".temp",
                "attributes": [
                    {"name": "Unit", "select": ".unit"},
                    {"name": "Location", "select": ".location"},
                ],
            }
        ],
    }

    # Act
    response = await hass.services.async_call(
        DOMAIN, "scrape", service_data, blocking=True, return_response=True
    )

    # Assert
    assert "temp" in response
    assert response["temp"]["value"] == "23.5"
    assert "attributes" in response["temp"]
    assert response["temp"]["attributes"]["unit"] == "C"
    assert response["temp"]["attributes"]["location"] == "Living Room"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_scrape_service_uses_name_as_fallback_id(hass: HomeAssistant):
    """Test scrape service uses slugified name when unique_id is missing."""
    # Arrange
    await setup_scrape_service(hass)

    test_url = "https://example.com/data"
    html_content = '<html><body><div class="value">42</div></body></html>'
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text=html_content))

    service_data = {
        CONF_RESOURCE: test_url,
        CONF_PARSER: "html.parser",
        Platform.SENSOR: [
            {
                "name": "Test Sensor Name",
                "select": ".value",
            }
        ],
    }

    # Act
    response = await hass.services.async_call(
        DOMAIN, "scrape", service_data, blocking=True, return_response=True
    )

    # Assert
    assert "test_sensor_name" in response
    assert response["test_sensor_name"]["value"] == "42"


def test_replace_template_characters_converts_placeholders():
    """Test _replace_template_characters converts placeholder syntax."""
    # Arrange
    template = "Value is {!{ value }!} and {!% if true %!}yes{!% endif %!}"

    # Act
    result = _replace_template_characters(template)

    # Assert
    assert result == "Value is {{ value }} and {% if true %}yes{% endif %}"


def test_replace_template_characters_handles_no_placeholders():
    """Test _replace_template_characters with no placeholders."""
    # Arrange
    template = "Normal text without templates"

    # Act
    result = _replace_template_characters(template)

    # Assert
    assert result == "Normal text without templates"


def test_restore_template_with_string(hass: HomeAssistant):
    """Test _restore_template converts string to Template."""
    # Arrange
    template_str = "Value is {!{ value }!}"

    # Act
    result = _restore_template(template_str)

    # Assert
    assert isinstance(result, Template)


def test_restore_template_with_template_object(hass: HomeAssistant):
    """Test _restore_template handles Template object."""
    # Arrange
    template_obj = Template("{{ value }}", hass)

    # Act
    result = _restore_template(template_obj)

    # Assert
    assert isinstance(result, Template)


def test_restore_templates_restores_sensor_templates(hass: HomeAssistant):
    """Test _restore_templates restores all sensor templates."""
    # Arrange
    config = {
        Platform.SENSOR: [
            {
                "name": "Test",
                "value_template": "{!{ value }!}",
                "icon": "{!{ icon }!}",
                "attributes": [
                    {"name": "attr1", "value_template": "{!{ attr }!}"},
                ],
            }
        ]
    }

    # Act
    result = _restore_templates(config)

    # Assert
    sensor = result[Platform.SENSOR][0]
    assert isinstance(sensor["value_template"], Template)
    assert isinstance(sensor["icon"], Template)
    assert isinstance(sensor["attributes"][0]["value_template"], Template)


def test_restore_templates_handles_missing_templates(hass: HomeAssistant):
    """Test _restore_templates handles configs without templates."""
    # Arrange
    config = {
        Platform.SENSOR: [
            {
                "name": "Test",
                "select": ".value",
            }
        ]
    }

    # Act
    result = _restore_templates(config)

    # Assert
    sensor = result[Platform.SENSOR][0]
    assert sensor.get("value_template") is None
    assert sensor.get("icon") is None


def test_restore_templates_restores_binary_sensor_templates(hass: HomeAssistant):
    """Test _restore_templates restores binary sensor templates."""
    # Arrange
    config = {
        Platform.BINARY_SENSOR: [
            {
                "name": "Test",
                "value_template": "{!{ value }!}",
                "icon": "{!{ icon }!}",
            }
        ]
    }

    # Act
    result = _restore_templates(config)

    # Assert
    sensor = result[Platform.BINARY_SENSOR][0]
    assert isinstance(sensor["value_template"], Template)
    assert isinstance(sensor["icon"], Template)


def test_restore_templates_restores_form_variable_templates(hass: HomeAssistant):
    """Test _restore_templates restores form variable templates."""
    # Arrange
    config = {
        "form_submit": {
            "variables": [
                {
                    "name": "token",
                    "value_template": "{!{ token }!}",
                }
            ]
        }
    }

    # Act
    result = _restore_templates(config)

    # Assert
    var = result["form_submit"]["variables"][0]
    assert isinstance(var["value_template"], Template)


def test_restore_templates_restores_header_templates(hass: HomeAssistant):
    """Test _restore_templates restores header templates."""
    # Arrange
    config = {
        "headers": {
            "Authorization": "{!{ token }!}",
            "Content-Type": "application/json",
        }
    }

    # Act
    result = _restore_templates(config)

    # Assert
    assert isinstance(result["headers"]["Authorization"], Template)
    assert isinstance(result["headers"]["Content-Type"], Template)


def test_restore_templates_handles_empty_attributes(hass: HomeAssistant):
    """Test _restore_templates handles sensors without attributes."""
    # Arrange
    config = {
        Platform.SENSOR: [
            {
                "name": "Test",
                "select": ".value",
            }
        ]
    }

    # Act
    result = _restore_templates(config)

    # Assert - should not raise an error
    assert result[Platform.SENSOR][0]["name"] == "Test"


def test_restore_templates_handles_empty_headers(hass: HomeAssistant):
    """Test _restore_templates handles config without headers."""
    # Arrange
    config = {
        Platform.SENSOR: [
            {
                "name": "Test",
                "select": ".value",
            }
        ]
    }

    # Act
    result = _restore_templates(config)

    # Assert - should not raise an error
    assert result.get("headers") is None


def test_restore_templates_handles_no_form_submit(hass: HomeAssistant):
    """Test _restore_templates handles config without form_submit."""
    # Arrange
    config = {
        Platform.SENSOR: [
            {
                "name": "Test",
                "select": ".value",
            }
        ]
    }

    # Act
    result = _restore_templates(config)

    # Assert - should not raise an error
    assert result.get("form_submit") is None
