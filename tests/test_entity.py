"""Integration tests for MultiscrapeEntity base class functionality."""

import pytest
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import (CONF_EXTRACT, CONF_ON_ERROR,
                                                 CONF_ON_ERROR_DEFAULT,
                                                 CONF_ON_ERROR_LOG,
                                                 CONF_ON_ERROR_VALUE,
                                                 CONF_ON_ERROR_VALUE_DEFAULT,
                                                 CONF_ON_ERROR_VALUE_LAST,
                                                 CONF_ON_ERROR_VALUE_NONE,
                                                 CONF_SELECT)
from custom_components.multiscrape.sensor import MultiscrapeSensor

from .fixtures.html_samples import SAMPLE_HTML_FULL


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
