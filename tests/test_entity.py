"""Integration tests for MultiscrapeEntity base class functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import (CONF_EXTRACT, CONF_ON_ERROR,
                                                 CONF_ON_ERROR_DEFAULT,
                                                 CONF_ON_ERROR_LOG,
                                                 CONF_ON_ERROR_VALUE,
                                                 CONF_ON_ERROR_VALUE_DEFAULT,
                                                 CONF_ON_ERROR_VALUE_LAST,
                                                 CONF_ON_ERROR_VALUE_NONE,
                                                 CONF_SELECT)
from custom_components.multiscrape.selector import Selector
from custom_components.multiscrape.sensor import MultiscrapeSensor

from .fixtures.html_samples import SAMPLE_HTML_FULL


def _create_sensor(hass, coordinator, scraper, attribute_selectors=None, icon_template=None):
    """Create a MultiscrapeSensor for testing."""
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }
    sensor_selector = Selector(hass, config)

    return MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test",
        name="test",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=icon_template,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors=attribute_selectors or {},
    )


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_entity_icon_template_rendering(hass: HomeAssistant, coordinator, scraper):
    """Test entity _set_icon renders icon template correctly."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    icon_template = Template(
        "{% if value > 50 %}mdi:alert{% else %}mdi:check{% endif %}", hass
    )

    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }
    sensor_selector = Selector(hass, config)

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test",
        name="test",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=icon_template,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # Act - test with value > 50
    sensor._set_icon(60)
    icon1 = sensor._attr_icon

    # Act - test with value <= 50
    sensor._set_icon(30)
    icon2 = sensor._attr_icon

    # Assert
    assert icon1 == "mdi:alert"
    assert icon2 == "mdi:check"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_entity_icon_template_error_handling(hass: HomeAssistant, coordinator, scraper, caplog):
    """Test entity _set_icon handles TemplateError gracefully."""
    from custom_components.multiscrape.selector import Selector

    # Arrange - template that will raise an error
    icon_template = Template("{{ value | invalid_filter }}", hass)

    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }
    sensor_selector = Selector(hass, config)

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test",
        name="test",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=icon_template,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # Act
    sensor._set_icon(42)

    # Assert - should log error but not crash
    assert "Exception occurred when rendering icon template" in caplog.text


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_entity_attribute_on_error_value_none(hass: HomeAssistant, coordinator, scraper):
    """Test entity attribute with on_error value set to 'none'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }

    attr_config = {
        CONF_NAME: "broken_attr",
        CONF_SELECT: Template(".nonexistent", hass),
        CONF_EXTRACT: "text",
        CONF_ON_ERROR: {
            CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_NONE,
            CONF_ON_ERROR_LOG: "warning",
        },
    }

    sensor_selector = Selector(hass, config)
    attribute_selectors = {"broken_attr": Selector(hass, attr_config)}

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test",
        name="test",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors=attribute_selectors,
    )

    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()
    sensor._update_attributes()

    # Assert - attribute should be None
    assert sensor._attr_extra_state_attributes.get("broken_attr") is None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_entity_attribute_on_error_value_last(hass: HomeAssistant, coordinator, scraper):
    """Test entity attribute with on_error value set to 'last'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }

    # First set to a value that exists, then to one that doesn't
    attr_config_working = {
        CONF_NAME: "test_attr",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }

    attr_config_broken = {
        CONF_NAME: "test_attr",
        CONF_SELECT: Template(".nonexistent", hass),
        CONF_EXTRACT: "text",
        CONF_ON_ERROR: {
            CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_LAST,
            CONF_ON_ERROR_LOG: "warning",
        },
    }

    sensor_selector = Selector(hass, config)

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test",
        name="test",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={"test_attr": Selector(hass, attr_config_working)},
    )

    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act - first update with working selector
    sensor._update_sensor()
    sensor._update_attributes()
    first_value = sensor._attr_extra_state_attributes.get("test_attr")

    # Change to broken selector
    sensor._attribute_selectors = {"test_attr": Selector(hass, attr_config_broken)}

    # Update again (should keep last value)
    sensor._update_attributes()
    second_value = sensor._attr_extra_state_attributes.get("test_attr")

    # Assert - should keep the last value
    assert first_value == "Current Version: 2024.8.3"
    assert second_value == "Current Version: 2024.8.3"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_entity_attribute_on_error_value_default(hass: HomeAssistant, coordinator, scraper):
    """Test entity attribute with on_error value set to 'default'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }

    attr_config = {
        CONF_NAME: "broken_attr",
        CONF_SELECT: Template(".nonexistent", hass),
        CONF_EXTRACT: "text",
        CONF_ON_ERROR: {
            CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_DEFAULT,
            CONF_ON_ERROR_DEFAULT: Template("fallback_value", hass),
            CONF_ON_ERROR_LOG: "warning",
        },
    }

    sensor_selector = Selector(hass, config)
    attribute_selectors = {"broken_attr": Selector(hass, attr_config)}

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test",
        name="test",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors=attribute_selectors,
    )

    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()
    sensor._update_attributes()

    # Assert - attribute should have default value
    assert sensor._attr_extra_state_attributes.get("broken_attr") == "fallback_value"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_entity_attribute_error_logging_disabled(hass: HomeAssistant, coordinator, scraper, caplog):
    """Test entity attribute error logging can be disabled."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }

    # Set log to false to disable error logging
    attr_config = {
        CONF_NAME: "broken_attr",
        CONF_SELECT: Template(".nonexistent", hass),
        CONF_EXTRACT: "text",
        CONF_ON_ERROR: {
            CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_NONE,
            CONF_ON_ERROR_LOG: False,  # Disable logging
        },
    }

    sensor_selector = Selector(hass, config)
    attribute_selectors = {"broken_attr": Selector(hass, attr_config)}

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test",
        name="test",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors=attribute_selectors,
    )

    await scraper.set_content(SAMPLE_HTML_FULL)
    caplog.clear()

    # Act
    sensor._update_sensor()
    sensor._update_attributes()

    # Assert - "Unable to extract" message should not be logged
    assert "Unable to extract data from HTML" not in caplog.text


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_entity_attribute_error_logging_custom_level(hass: HomeAssistant, coordinator, scraper, caplog):
    """Test entity attribute error logging with custom log level."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }

    attr_config = {
        CONF_NAME: "broken_attr",
        CONF_SELECT: Template(".nonexistent", hass),
        CONF_EXTRACT: "text",
        CONF_ON_ERROR: {
            CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_NONE,
            CONF_ON_ERROR_LOG: "error",  # Custom log level
        },
    }

    sensor_selector = Selector(hass, config)
    attribute_selectors = {"broken_attr": Selector(hass, attr_config)}

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test",
        name="test",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors=attribute_selectors,
    )

    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()
    sensor._update_attributes()

    # Assert - error should be logged with ERROR level
    assert "Unable to extract data from HTML" in caplog.text


# ============================================================================
# _handle_coordinator_update callback tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_handle_coordinator_update_success_sets_available_and_updates(
    hass: HomeAssistant, coordinator, scraper
):
    """Test that a successful coordinator update sets entity available and updates value."""
    sensor = _create_sensor(hass, coordinator, scraper)
    sensor.async_write_ha_state = MagicMock()

    await scraper.set_content(SAMPLE_HTML_FULL)
    coordinator._last_update_success = True
    coordinator.update_error = False

    # Act - call the actual callback as the coordinator listener would
    sensor._handle_coordinator_update()

    # Assert
    assert sensor._attr_available is True
    assert sensor._attr_native_value == "Current Version: 2024.8.3"
    sensor.async_write_ha_state.assert_called_once()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_handle_coordinator_update_failure_sets_unavailable(
    hass: HomeAssistant, coordinator, scraper
):
    """Test that a failed coordinator update makes entity unavailable without clobbering value."""
    sensor = _create_sensor(hass, coordinator, scraper)
    sensor.async_write_ha_state = MagicMock()

    # Set an initial value
    sensor._attr_native_value = "previous_value"

    # Simulate failed update
    coordinator._last_update_success = False

    # Act
    sensor._handle_coordinator_update()

    # Assert - unavailable but value preserved
    assert sensor._attr_available is False
    assert sensor._attr_native_value == "previous_value"
    sensor.async_write_ha_state.assert_called_once()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_handle_coordinator_update_always_writes_state(
    hass: HomeAssistant, coordinator, scraper
):
    """Test that async_write_ha_state is always called, for both success and failure."""
    sensor = _create_sensor(hass, coordinator, scraper)
    sensor.async_write_ha_state = MagicMock()

    # Success case
    await scraper.set_content(SAMPLE_HTML_FULL)
    coordinator._last_update_success = True
    coordinator.update_error = False
    sensor._handle_coordinator_update()
    assert sensor.async_write_ha_state.call_count == 1

    # Failure case
    coordinator._last_update_success = False
    sensor._handle_coordinator_update()
    assert sensor.async_write_ha_state.call_count == 2


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_handle_coordinator_update_updates_attributes_with_form_variables(
    hass: HomeAssistant, coordinator, scraper, content_request_manager
):
    """Test that form variables from the coordinator are passed to scraper during attribute update."""
    attr_config = {
        CONF_NAME: "version_attr",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }
    attribute_selectors = {"version_attr": Selector(hass, attr_config)}
    sensor = _create_sensor(hass, coordinator, scraper, attribute_selectors=attribute_selectors)
    sensor.async_write_ha_state = MagicMock()

    # Set form variables on the request manager
    content_request_manager._form_variables = {"token": "abc123"}

    await scraper.set_content(SAMPLE_HTML_FULL)
    coordinator._last_update_success = True
    coordinator.update_error = False

    # Act
    sensor._handle_coordinator_update()

    # Assert - attribute was scraped and set
    assert sensor._attr_extra_state_attributes["version_attr"] == "Current Version: 2024.8.3"


# ============================================================================
# async_added_to_hass state restoration tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_added_to_hass_restores_state_and_attributes(
    hass: HomeAssistant, coordinator, scraper
):
    """Test that async_added_to_hass restores previous state and attributes."""
    attr_config = {
        CONF_NAME: "test_attr",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }
    attribute_selectors = {"test_attr": Selector(hass, attr_config)}
    sensor = _create_sensor(hass, coordinator, scraper, attribute_selectors=attribute_selectors)

    # Mock the state restoration
    mock_state = State("sensor.test", "42.0", {"test_attr": "saved_value"})
    with patch.object(sensor, "async_get_last_state", new=AsyncMock(return_value=mock_state)):
        await sensor.async_added_to_hass()

    # Assert
    assert sensor._attr_native_value == "42.0"
    assert sensor._attr_extra_state_attributes["test_attr"] == "saved_value"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_added_to_hass_no_previous_state(
    hass: HomeAssistant, coordinator, scraper
):
    """Test that async_added_to_hass handles no previous state gracefully."""
    sensor = _create_sensor(hass, coordinator, scraper)
    initial_value = sensor._attr_native_value

    with patch.object(sensor, "async_get_last_state", new=AsyncMock(return_value=None)):
        await sensor.async_added_to_hass()

    # Assert - value unchanged
    assert sensor._attr_native_value == initial_value


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_added_to_hass_registers_coordinator_listener(
    hass: HomeAssistant, coordinator, scraper
):
    """Test that async_added_to_hass registers the coordinator update listener."""
    sensor = _create_sensor(hass, coordinator, scraper)

    with patch.object(sensor, "async_get_last_state", new=AsyncMock(return_value=None)), \
         patch.object(coordinator, "async_add_listener", return_value=lambda: None) as mock_listener:
        await sensor.async_added_to_hass()

    # Assert - listener was registered with the callback
    mock_listener.assert_called_once_with(sensor._handle_coordinator_update)
