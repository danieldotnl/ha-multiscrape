"""Integration tests for sensor platform."""

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (CONF_DEVICE_CLASS, CONF_FORCE_UPDATE,
                                 CONF_ICON, CONF_NAME, CONF_UNIQUE_ID,
                                 CONF_UNIT_OF_MEASUREMENT)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import (CONF_ON_ERROR,
                                                 CONF_ON_ERROR_DEFAULT,
                                                 CONF_ON_ERROR_VALUE,
                                                 CONF_ON_ERROR_VALUE_DEFAULT,
                                                 CONF_ON_ERROR_VALUE_LAST,
                                                 CONF_ON_ERROR_VALUE_NONE,
                                                 CONF_PICTURE, CONF_SELECT,
                                                 CONF_STATE_CLASS)
from custom_components.multiscrape.sensor import (MultiscrapeSensor,
                                                  async_setup_platform)

from .fixtures.html_samples import SAMPLE_HTML_FULL


@pytest.fixture
def sensor_config(hass: HomeAssistant):
    """Create a basic sensor configuration."""
    from custom_components.multiscrape.const import CONF_EXTRACT

    return {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_UNIQUE_ID: "test_sensor_unique_id",
        CONF_UNIT_OF_MEASUREMENT: "version",
        CONF_EXTRACT: "text",
    }


@pytest.fixture
def discovery_info():
    """Create discovery info for platform setup."""
    return {"name": "test_scraper"}


@pytest.fixture
def setup_sensor(hass: HomeAssistant, coordinator, scraper, sensor_config):
    """Create a MultiscrapeSensor instance for testing."""
    from custom_components.multiscrape.selector import Selector

    sensor_selector = Selector(hass, sensor_config)

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id=sensor_config.get(CONF_UNIQUE_ID),
        name=sensor_config[CONF_NAME],
        unit_of_measurement=sensor_config.get(CONF_UNIT_OF_MEASUREMENT),
        device_class=sensor_config.get(CONF_DEVICE_CLASS),
        state_class=sensor_config.get(CONF_STATE_CLASS),
        force_update=sensor_config.get(CONF_FORCE_UPDATE),
        icon_template=sensor_config.get(CONF_ICON),
        picture=sensor_config.get(CONF_PICTURE),
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    return sensor


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_initialization(setup_sensor):
    """Test sensor initializes with correct attributes."""
    # Arrange & Act
    sensor = setup_sensor

    # Assert
    assert sensor._name == "test_sensor"
    assert sensor._attr_unique_id == "test_sensor_unique_id"
    assert sensor._attr_native_unit_of_measurement == "version"
    assert sensor._attr_should_poll is False
    assert sensor.entity_id == "sensor.test_sensor_unique_id"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_update_successful(hass: HomeAssistant, setup_sensor, scraper):
    """Test sensor updates successfully with scraped data."""
    # Arrange
    sensor = setup_sensor
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()

    # Assert
    assert sensor._attr_native_value == "Current Version: 2024.8.3"
    assert sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_with_date_device_class(hass: HomeAssistant, coordinator, scraper):
    """Test sensor with DATE device class parses dates."""
    from datetime import date

    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange - Use ISO format date that HA can parse
    html_with_iso_date = '<div class="iso-date">2024-01-17</div>'
    config = {
        CONF_NAME: "test_date_sensor",
        CONF_SELECT: Template(".iso-date", hass),
        CONF_EXTRACT: "text",
        CONF_DEVICE_CLASS: SensorDeviceClass.DATE,
    }

    sensor_selector = Selector(hass, config)
    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_date_sensor",
        name="test_date_sensor",
        unit_of_measurement=None,
        device_class=SensorDeviceClass.DATE,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(html_with_iso_date)

    # Act
    sensor._update_sensor()

    # Assert - async_parse_date_datetime should parse the ISO date string
    assert sensor._attr_native_value is not None
    assert isinstance(sensor._attr_native_value, date)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_on_error_value_none(hass: HomeAssistant, coordinator, scraper):
    """Test sensor with on_error value set to 'none'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".nonexistent-selector", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_NONE},
    }

    sensor_selector = Selector(hass, config)
    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_sensor",
        name="test_sensor",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()

    # Assert
    assert sensor._attr_available is False


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_on_error_value_last(hass: HomeAssistant, coordinator, scraper):
    """Test sensor with on_error value set to 'last'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".nonexistent-selector", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_LAST},
    }

    sensor_selector = Selector(hass, config)
    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_sensor",
        name="test_sensor",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # Set initial value
    sensor._attr_native_value = "previous_value"
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()

    # Assert - should keep the last value
    assert sensor._attr_native_value == "previous_value"
    assert sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_on_error_value_last_with_none_value(hass: HomeAssistant, coordinator, scraper):
    """Test sensor with on_error value 'last' but no previous value."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".nonexistent-selector", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_LAST},
    }

    sensor_selector = Selector(hass, config)
    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_sensor",
        name="test_sensor",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # Don't set initial value, _attr_native_value defaults to None
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()

    # Assert - should be unavailable when trying to keep last value but it's None
    assert sensor._attr_native_value is None
    assert sensor._attr_available is False


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_on_error_value_default(hass: HomeAssistant, coordinator, scraper):
    """Test sensor with on_error value set to 'default'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    default_template = Template("{{ 'fallback_value' }}", hass)
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".nonexistent-selector", hass),
        CONF_ON_ERROR: {
            CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_DEFAULT,
            CONF_ON_ERROR_DEFAULT: default_template,
        },
    }

    sensor_selector = Selector(hass, config)
    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_sensor",
        name="test_sensor",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()

    # Assert
    assert sensor._attr_native_value == "fallback_value"
    assert sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_update_with_coordinator_error(hass: HomeAssistant, coordinator, scraper, setup_sensor):
    """Test sensor update when coordinator has an error."""
    # Arrange
    sensor = setup_sensor
    coordinator.update_error = True
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()

    # Assert - should handle error gracefully
    assert sensor._attr_available is False


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_with_icon_template(hass: HomeAssistant, coordinator, scraper):
    """Test sensor with dynamic icon template."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    icon_template = Template("{% if value == '2024.8.3' %}mdi:check{% else %}mdi:alert{% endif %}", hass)
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
    }

    sensor_selector = Selector(hass, config)
    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_sensor",
        name="test_sensor",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=icon_template,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # We need to manually set content that will be scraped to get "2024.8.3"
    # First, let's set simpler content to test the icon rendering
    await scraper.set_content('<div class="current-version"><h1>2024.8.3</h1></div>')

    # Act
    sensor._update_sensor()

    # Assert - icon should be set based on value
    # The exact icon depends on the value scraped
    assert sensor._attr_icon is not None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_with_picture(hass: HomeAssistant, coordinator, scraper, sensor_config):
    """Test sensor with entity picture configured."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    sensor_config[CONF_PICTURE] = "/local/test_picture.png"
    sensor_selector = Selector(hass, sensor_config)

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_sensor",
        name="test_sensor",
        unit_of_measurement=None,
        device_class=None,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture="/local/test_picture.png",
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # Assert
    assert sensor._attr_entity_picture == "/local/test_picture.png"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_with_attributes(hass: HomeAssistant, coordinator, scraper):
    """Test sensor with additional attributes."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_sensor",
        CONF_SELECT: Template(".current-version h1", hass),
        CONF_EXTRACT: "text",
    }

    attr_config = {
        CONF_NAME: "release_date",
        CONF_SELECT: Template(".release-date", hass),
        CONF_EXTRACT: "text",
    }

    sensor_selector = Selector(hass, config)
    attribute_selectors = {"release_date": Selector(hass, attr_config)}

    sensor = MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_sensor",
        name="test_sensor",
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

    # Assert
    assert sensor._attr_native_value == "Current Version: 2024.8.3"
    assert "release_date" in sensor._attr_extra_state_attributes
    assert sensor._attr_extra_state_attributes["release_date"] == "January 17, 2022"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_setup_platform_raises_platform_not_ready(
    hass: HomeAssistant, coordinator, mock_http_wrapper
):
    """Test async_setup_platform raises PlatformNotReady when coordinator fails."""
    # Arrange
    coordinator.last_update_success = False

    # We need to mock async_get_config_and_coordinator to return our fixtures
    async def mock_get_config_and_coordinator(hass, platform, discovery_info):
        from custom_components.multiscrape.const import DEFAULT_SEPARATOR
        from custom_components.multiscrape.scraper import Scraper

        config = {
            CONF_NAME: "test_sensor",
            CONF_SELECT: Template(".test", hass),
        }
        scraper = Scraper("test_scraper", hass, None, "lxml", DEFAULT_SEPARATOR)
        return config, coordinator, scraper

    # Patch the function
    import custom_components.multiscrape.sensor as sensor_module
    original_func = sensor_module.async_get_config_and_coordinator
    sensor_module.async_get_config_and_coordinator = mock_get_config_and_coordinator

    entities_added = []

    def mock_add_entities(entities):
        entities_added.extend(entities)

    # Act & Assert
    with pytest.raises(PlatformNotReady):
        await async_setup_platform(
            hass,
            {},
            mock_add_entities,
            discovery_info={"name": "test"},
        )

    # Cleanup
    sensor_module.async_get_config_and_coordinator = original_func
