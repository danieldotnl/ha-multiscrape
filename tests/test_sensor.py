"""Integration tests for sensor platform."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (CONF_DEVICE_CLASS, CONF_FORCE_UPDATE,
                                 CONF_ICON, CONF_NAME, CONF_UNIQUE_ID,
                                 CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import (CONF_EXTRACT, CONF_ON_ERROR,
                                                 CONF_ON_ERROR_DEFAULT,
                                                 CONF_ON_ERROR_VALUE,
                                                 CONF_ON_ERROR_VALUE_DEFAULT,
                                                 CONF_ON_ERROR_VALUE_LAST,
                                                 CONF_ON_ERROR_VALUE_NONE,
                                                 CONF_PICTURE, CONF_SELECT,
                                                 CONF_STATE_CLASS)
from custom_components.multiscrape.selector import Selector
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
    assert sensor.should_poll is False
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
    assert sensor._scrape_error is False


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
    assert sensor._scrape_error is True


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
    assert sensor._scrape_error is False


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
    assert sensor._scrape_error is True


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
    assert sensor._scrape_error is False


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
    assert sensor._scrape_error is True


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
    hass: HomeAssistant, coordinator, mock_http_session
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




# ============================================================================
# Date / timestamp device class (#623)
# ============================================================================


def _create_date_sensor(hass, coordinator, scraper, device_class, extra_config=None):
    """Create a sensor with a date/timestamp device class."""
    config = {
        CONF_NAME: "test_date_sensor",
        CONF_SELECT: Template(".iso-date", hass),
        CONF_EXTRACT: "text",
        CONF_DEVICE_CLASS: device_class,
        **(extra_config or {}),
    }

    return MultiscrapeSensor(
        hass=hass,
        coordinator=coordinator,
        scraper=scraper,
        unique_id="test_date_sensor",
        name="test_date_sensor",
        unit_of_measurement=None,
        device_class=device_class,
        state_class=None,
        force_update=False,
        icon_template=None,
        picture=None,
        sensor_selector=Selector(hass, config),
        attribute_selectors={},
    )


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.parametrize(
    ("device_class", "restored", "expected"),
    [
        (
            SensorDeviceClass.TIMESTAMP,
            "2026-09-21T10:29:00+00:00",
            datetime(2026, 9, 21, 10, 29, tzinfo=UTC),
        ),
        (SensorDeviceClass.DATE, "2026-09-21", date(2026, 9, 21)),
    ],
)
async def test_sensor_restores_date_device_class_as_native_type(
    hass: HomeAssistant, coordinator, scraper, device_class, restored, expected
):
    """A restored state string must be parsed before it becomes the native value.

    Restored states are always strings, so handing one straight to a
    date/timestamp sensor made HA reject the entity on startup with
    "has timestamp device class but provides state ... 'str' object has
    no attribute 'tzinfo'" (#623).
    """
    # Arrange
    sensor = _create_date_sensor(hass, coordinator, scraper, device_class)

    # Act
    mock_state = State(sensor.entity_id, restored)
    with patch.object(
        sensor, "async_get_last_state", new=AsyncMock(return_value=mock_state)
    ):
        await sensor.async_added_to_hass()

    # Assert - the native value is a date/datetime, and HA can write the state
    assert sensor._attr_native_value == expected
    assert sensor.state == restored


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_restores_unparsable_state_as_none(
    hass: HomeAssistant, coordinator, scraper
):
    """An unparsable restored state degrades to no value, rather than raising."""
    # Arrange
    sensor = _create_date_sensor(
        hass, coordinator, scraper, SensorDeviceClass.TIMESTAMP
    )

    # Act
    mock_state = State(sensor.entity_id, "not a timestamp")
    with patch.object(
        sensor, "async_get_last_state", new=AsyncMock(return_value=mock_state)
    ):
        await sensor.async_added_to_hass()

    # Assert
    assert sensor._attr_native_value is None
    assert sensor.state is None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_timestamp_device_class_parses_scraped_value(
    hass: HomeAssistant, coordinator, scraper
):
    """Test sensor with TIMESTAMP device class parses scraped timestamps."""
    # Arrange
    sensor = _create_date_sensor(
        hass, coordinator, scraper, SensorDeviceClass.TIMESTAMP
    )
    await scraper.set_content('<div class="iso-date">2026-09-21T10:29:00+00:00</div>')

    # Act
    sensor._update_sensor()

    # Assert
    assert sensor._attr_native_value == datetime(2026, 9, 21, 10, 29, tzinfo=UTC)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_timestamp_device_class_on_error_default_is_parsed(
    hass: HomeAssistant, coordinator, scraper
):
    """An on_error default must be parsed too, or it crashes the state write."""
    # Arrange - a selector that finds nothing, falling back to the default
    sensor = _create_date_sensor(
        hass,
        coordinator,
        scraper,
        SensorDeviceClass.TIMESTAMP,
        {
            CONF_SELECT: Template(".does-not-exist", hass),
            CONF_ON_ERROR: {
                CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_DEFAULT,
                CONF_ON_ERROR_DEFAULT: Template("2026-01-01T00:00:00+00:00", hass),
            },
        },
    )
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act
    sensor._update_sensor()

    # Assert
    assert sensor._attr_native_value == datetime(2026, 1, 1, tzinfo=UTC)
    assert sensor.state == "2026-01-01T00:00:00+00:00"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_timestamp_device_class_unconvertible_value_uses_on_error(
    hass: HomeAssistant, coordinator, scraper
):
    """A value that cannot be converted must go through `on_error`.

    A `value_template` renders with `parse_result=True`, so it can yield
    an int, float or None. Those cannot be parsed into a timestamp at
    all, and dropping the state instead of consulting `on_error` would
    silently discard a good previous value.
    """
    # Arrange - the template turns the scraped text into a plain int
    sensor = _create_date_sensor(
        hass,
        coordinator,
        scraper,
        SensorDeviceClass.TIMESTAMP,
        {
            CONF_VALUE_TEMPLATE: Template("{{ value | int }}", hass),
            CONF_ON_ERROR: {CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_LAST},
        },
    )
    previous = datetime(2026, 9, 21, 10, 29, tzinfo=UTC)
    sensor._attr_native_value = previous
    await scraper.set_content('<div class="iso-date">1758450540</div>')

    # Act
    sensor._update_sensor()

    # Assert - on_error kept the last good value
    assert sensor._attr_native_value == previous


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_sensor_timestamp_device_class_unconvertible_default_is_handled(
    hass: HomeAssistant, coordinator, scraper
):
    """An on_error default that is not a timestamp must not escape the handler.

    The default is applied from inside `_update_sensor`'s `except`
    block, so an exception there would propagate out of the coordinator
    callback and the state would never be written.
    """
    # Arrange - nothing to select, and a numeric default for a timestamp
    sensor = _create_date_sensor(
        hass,
        coordinator,
        scraper,
        SensorDeviceClass.TIMESTAMP,
        {
            CONF_SELECT: Template(".does-not-exist", hass),
            CONF_ON_ERROR: {
                CONF_ON_ERROR_VALUE: CONF_ON_ERROR_VALUE_DEFAULT,
                CONF_ON_ERROR_DEFAULT: Template("{{ 0 }}", hass),
            },
        },
    )
    await scraper.set_content(SAMPLE_HTML_FULL)

    # Act - must not raise
    sensor._update_sensor()

    # Assert - no value, and the entity reports itself unavailable
    assert sensor._attr_native_value is None
    assert sensor._scrape_error is True
