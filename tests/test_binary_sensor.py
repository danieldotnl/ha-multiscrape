"""Integration tests for binary sensor platform."""

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (CONF_DEVICE_CLASS, CONF_FORCE_UPDATE,
                                 CONF_ICON, CONF_NAME, CONF_UNIQUE_ID)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.template import Template

from custom_components.multiscrape.binary_sensor import (
    MultiscrapeBinarySensor, async_setup_platform)
from custom_components.multiscrape.const import (CONF_ON_ERROR,
                                                 CONF_ON_ERROR_DEFAULT,
                                                 CONF_ON_ERROR_VALUE,
                                                 CONF_ON_ERROR_VALUE_DEFAULT,
                                                 CONF_ON_ERROR_VALUE_LAST,
                                                 CONF_ON_ERROR_VALUE_NONE,
                                                 CONF_PICTURE, CONF_SELECT)

from .fixtures.html_samples import SAMPLE_HTML_FULL


@pytest.fixture
def binary_sensor_config(hass: HomeAssistant):
    """Create a basic binary sensor configuration."""
    from custom_components.multiscrape.const import CONF_EXTRACT

    return {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".availability", hass),
        CONF_UNIQUE_ID: "test_binary_sensor_unique_id",
        CONF_EXTRACT: "text",
    }


@pytest.fixture
def discovery_info():
    """Create discovery info for platform setup."""
    return {"name": "test_scraper"}


@pytest.fixture
def setup_binary_sensor(hass: HomeAssistant, coordinator, scraper, binary_sensor_config):
    """Create a MultiscrapeBinarySensor instance for testing."""
    from custom_components.multiscrape.selector import Selector

    sensor_selector = Selector(hass, binary_sensor_config)

    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id=binary_sensor_config.get(CONF_UNIQUE_ID),
        name=binary_sensor_config[CONF_NAME],
        device_class=binary_sensor_config.get(CONF_DEVICE_CLASS),
        force_update=binary_sensor_config.get(CONF_FORCE_UPDATE),
        icon_template=binary_sensor_config.get(CONF_ICON),
        picture=binary_sensor_config.get(CONF_PICTURE),
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    return binary_sensor


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_initialization(setup_binary_sensor):
    """Test binary sensor initializes with correct attributes."""
    # Arrange & Act
    binary_sensor = setup_binary_sensor

    # Assert
    assert binary_sensor._name == "test_binary_sensor"
    assert binary_sensor._attr_unique_id == "test_binary_sensor_unique_id"
    assert binary_sensor._attr_should_poll is False
    assert binary_sensor.entity_id == "binary_sensor.test_binary_sensor_unique_id"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_converts_integer_1_to_true(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor converts integer 1 to True."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange
    html_with_one = '<div class="status">1</div>'
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".status", hass),
        CONF_EXTRACT: "text",
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(html_with_one)

    # Act
    binary_sensor._update_sensor()

    # Assert
    assert binary_sensor._attr_is_on is True
    assert binary_sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_converts_integer_0_to_false(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor converts integer 0 to False."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange
    html_with_zero = '<div class="status">0</div>'
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".status", hass),
        CONF_EXTRACT: "text",
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(html_with_zero)

    # Act
    binary_sensor._update_sensor()

    # Assert
    assert binary_sensor._attr_is_on is False
    assert binary_sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.parametrize("true_value", ["true", "True", "TRUE", "on", "On", "ON", "yes", "Yes", "YES", "open", "Open", "OPEN"])
async def test_binary_sensor_converts_true_strings(hass: HomeAssistant, coordinator, scraper, true_value):
    """Test binary sensor converts various true string representations."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange
    html = f'<div class="status">{true_value}</div>'
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".status", hass),
        CONF_EXTRACT: "text",
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(html)

    # Act
    binary_sensor._update_sensor()

    # Assert
    assert binary_sensor._attr_is_on is True
    assert binary_sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.parametrize("false_value", ["false", "False", "FALSE", "off", "Off", "OFF", "no", "No", "NO", "closed", "Closed", "CLOSED"])
async def test_binary_sensor_converts_false_strings(hass: HomeAssistant, coordinator, scraper, false_value):
    """Test binary sensor converts various false string representations."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange
    html = f'<div class="status">{false_value}</div>'
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".status", hass),
        CONF_EXTRACT: "text",
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(html)

    # Act
    binary_sensor._update_sensor()

    # Assert
    assert binary_sensor._attr_is_on is False
    assert binary_sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_converts_unrecognized_string_to_false(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor converts unrecognized strings to False (default dict behavior)."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange - Use a string that's not in the recognized true values
    html = '<div class="status">maybe</div>'
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".status", hass),
        CONF_EXTRACT: "text",
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(html)

    # Act
    binary_sensor._update_sensor()

    # Assert - unrecognized strings default to False via .get(value.lower(), False)
    assert binary_sensor._attr_is_on is False
    assert binary_sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_on_error_value_none(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor with on_error value set to 'none'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".nonexistent-selector", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_NONE},
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    binary_sensor._update_sensor()

    # Assert
    assert binary_sensor._attr_available is False


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_on_error_value_last(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor with on_error value set to 'last'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".nonexistent-selector", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_LAST},
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # Set initial value
    binary_sensor._attr_is_on = True
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    binary_sensor._update_sensor()

    # Assert - should keep the last value
    assert binary_sensor._attr_is_on is True
    assert binary_sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_on_error_value_last_with_none_value(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor with on_error value 'last' but no previous value."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".nonexistent-selector", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_LAST},
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # Don't set initial value, _attr_is_on defaults to None
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    binary_sensor._update_sensor()

    # Assert - keeps last value (None) and remains available (returns early, no availability change)
    assert binary_sensor._attr_is_on is None
    assert binary_sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_on_error_value_default(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor with on_error value set to 'default'."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    default_template = Template("{{ 'true' }}", hass)
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".nonexistent-selector", hass),
        CONF_ON_ERROR: {
            CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_DEFAULT,
            CONF_ON_ERROR_DEFAULT: default_template,
        },
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    binary_sensor._update_sensor()

    # Assert - default value "true" should be converted to boolean True
    assert binary_sensor._attr_is_on is True
    assert binary_sensor._attr_available is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_update_with_coordinator_error(hass: HomeAssistant, coordinator, scraper, setup_binary_sensor):
    """Test binary sensor update when coordinator has an error."""
    # Arrange
    binary_sensor = setup_binary_sensor
    coordinator.update_error = True
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    binary_sensor._update_sensor()

    # Assert - should handle error gracefully
    assert binary_sensor._attr_available is False


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_with_device_class(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor with device class configured."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange
    html = '<div class="door">open</div>'
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".door", hass),
        CONF_EXTRACT: "text",
        CONF_DEVICE_CLASS: BinarySensorDeviceClass.DOOR,
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=BinarySensorDeviceClass.DOOR,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(html)

    # Act
    binary_sensor._update_sensor()

    # Assert
    assert binary_sensor._attr_is_on is True
    assert binary_sensor.device_class == BinarySensorDeviceClass.DOOR


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_with_icon_template(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor with dynamic icon template."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange
    icon_template = Template("{% if value %}mdi:door-open{% else %}mdi:door-closed{% endif %}", hass)
    html = '<div class="status">true</div>'
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".status", hass),
        CONF_EXTRACT: "text",
    }

    sensor_selector = Selector(hass, config)
    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=icon_template,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    await scraper.set_content(html)

    # Act
    binary_sensor._update_sensor()

    # Assert - icon should be set based on value
    assert binary_sensor._attr_icon is not None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_with_picture(hass: HomeAssistant, coordinator, scraper, binary_sensor_config):
    """Test binary sensor with entity picture configured."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    binary_sensor_config[CONF_PICTURE] = "/local/test_picture.png"
    sensor_selector = Selector(hass, binary_sensor_config)

    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture="/local/test_picture.png",
        sensor_selector=sensor_selector,
        attribute_selectors={},
    )

    # Assert
    assert binary_sensor._attr_entity_picture == "/local/test_picture.png"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_binary_sensor_with_attributes(hass: HomeAssistant, coordinator, scraper):
    """Test binary sensor with additional attributes."""
    from custom_components.multiscrape.const import CONF_EXTRACT
    from custom_components.multiscrape.selector import Selector

    # Arrange
    config = {
        CONF_NAME: "test_binary_sensor",
        CONF_SELECT: Template(".status", hass),
        CONF_EXTRACT: "text",
    }

    attr_config = {
        CONF_NAME: "last_changed",
        CONF_SELECT: Template(".timestamp", hass),
        CONF_EXTRACT: "text",
    }

    sensor_selector = Selector(hass, config)
    attribute_selectors = {"last_changed": Selector(hass, attr_config)}

    binary_sensor = MultiscrapeBinarySensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_binary_sensor",
        name="test_binary_sensor",
        device_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=sensor_selector,
        attribute_selectors=attribute_selectors,
    )

    html = '<div class="status">true</div><div class="timestamp">2024-01-17</div>'
    await scraper.set_content(html)

    # Act
    binary_sensor._update_sensor()
    binary_sensor._update_attributes()

    # Assert
    assert binary_sensor._attr_is_on is True
    assert "last_changed" in binary_sensor._attr_extra_state_attributes
    assert binary_sensor._attr_extra_state_attributes["last_changed"] == "2024-01-17"


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
            CONF_NAME: "test_binary_sensor",
            CONF_SELECT: Template(".test", hass),
        }
        scraper = Scraper("test_scraper", hass, None, "lxml", DEFAULT_SEPARATOR)
        return config, coordinator, scraper

    # Patch the function
    import custom_components.multiscrape.binary_sensor as binary_sensor_module
    original_func = binary_sensor_module.async_get_config_and_coordinator
    binary_sensor_module.async_get_config_and_coordinator = mock_get_config_and_coordinator

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
    binary_sensor_module.async_get_config_and_coordinator = original_func
