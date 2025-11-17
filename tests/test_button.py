"""Integration tests for button platform."""

import pytest
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from custom_components.multiscrape.button import (MultiscrapeRefreshButton,
                                                  async_setup_platform)


@pytest.fixture
def button_config():
    """Create a basic button configuration."""
    return {
        CONF_NAME: "test_refresh_button",
        CONF_UNIQUE_ID: "test_button_unique_id",
    }


@pytest.fixture
def discovery_info():
    """Create discovery info for platform setup."""
    return {"name": "test_scraper"}


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_button_initialization(hass: HomeAssistant, coordinator):
    """Test button initializes with correct attributes."""
    # Arrange & Act
    button = MultiscrapeRefreshButton(
        hass=hass,
        coordinator=coordinator,
        unique_id="test_button",
        name="Test Refresh Button",
    )

    # Assert
    assert button._attr_name == "Test Refresh Button"
    assert button._attr_unique_id == "test_button"
    assert button._attr_icon == "mdi:refresh"
    assert button._attr_entity_category == EntityCategory.CONFIG
    assert button._coordinator == coordinator
    assert button.entity_id == "button.test_button"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_button_initialization_without_unique_id(hass: HomeAssistant, coordinator):
    """Test button initializes using name when unique_id is None."""
    # Arrange & Act
    button = MultiscrapeRefreshButton(
        hass=hass,
        coordinator=coordinator,
        unique_id=None,
        name="Test Button Name",
    )

    # Assert
    assert button._attr_unique_id is None
    assert button.entity_id == "button.test_button_name"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_button_initialization_with_special_characters_in_name(
    hass: HomeAssistant, coordinator
):
    """Test button entity_id is slugified from name with special characters."""
    # Arrange & Act
    button = MultiscrapeRefreshButton(
        hass=hass,
        coordinator=coordinator,
        unique_id=None,
        name="Test Button: Special! Name?",
    )

    # Assert
    assert button._attr_name == "Test Button: Special! Name?"
    # Entity ID should be slugified
    assert "button.test_button_special_name" in button.entity_id


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_button_press_triggers_coordinator_refresh(
    hass: HomeAssistant, coordinator, caplog
):
    """Test pressing button triggers coordinator refresh."""
    # Arrange
    button = MultiscrapeRefreshButton(
        hass=hass,
        coordinator=coordinator,
        unique_id="test_button",
        name="Test Button",
    )

    # Track if refresh was called
    refresh_called = False

    async def mock_refresh():
        nonlocal refresh_called
        refresh_called = True

    coordinator.async_request_refresh = mock_refresh

    # Act
    await button.async_press()

    # Assert
    assert refresh_called is True
    assert "Multiscrape triggered by button" in caplog.text


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_setup_platform_creates_button(
    hass: HomeAssistant, coordinator, mock_http_wrapper, button_config, discovery_info
):
    """Test async_setup_platform creates button entity."""
    # Arrange
    entities_added = []

    def mock_add_entities(entities):
        entities_added.extend(entities)

    # Mock async_get_config_and_coordinator
    async def mock_get_config_and_coordinator(hass, platform, discovery_info):
        from custom_components.multiscrape.const import DEFAULT_SEPARATOR
        from custom_components.multiscrape.scraper import Scraper

        scraper = Scraper("test_scraper", hass, None, "lxml", DEFAULT_SEPARATOR)
        return button_config, coordinator, scraper

    # Patch the function
    import custom_components.multiscrape.button as button_module

    original_func = button_module.async_get_config_and_coordinator
    button_module.async_get_config_and_coordinator = mock_get_config_and_coordinator

    try:
        # Act
        await async_setup_platform(
            hass, button_config, mock_add_entities, discovery_info
        )

        # Assert
        assert len(entities_added) == 1
        button = entities_added[0]
        assert isinstance(button, MultiscrapeRefreshButton)
        assert button._attr_name == "test_refresh_button"
        assert button._attr_unique_id == "test_button_unique_id"
    finally:
        # Restore original function
        button_module.async_get_config_and_coordinator = original_func


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_button_has_config_entity_category(hass: HomeAssistant, coordinator):
    """Test button has CONFIG entity category (shows in settings, not main UI)."""
    # Arrange & Act
    button = MultiscrapeRefreshButton(
        hass=hass,
        coordinator=coordinator,
        unique_id="test_button",
        name="Test Button",
    )

    # Assert - EntityCategory.CONFIG means it shows in settings area
    assert button._attr_entity_category == EntityCategory.CONFIG


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_button_has_refresh_icon(hass: HomeAssistant, coordinator):
    """Test button uses refresh icon."""
    # Arrange & Act
    button = MultiscrapeRefreshButton(
        hass=hass,
        coordinator=coordinator,
        unique_id="test_button",
        name="Test Button",
    )

    # Assert
    assert button._attr_icon == "mdi:refresh"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_button_entity_id_format(hass: HomeAssistant, coordinator):
    """Test button entity ID follows platform format."""
    # Arrange & Act
    button = MultiscrapeRefreshButton(
        hass=hass,
        coordinator=coordinator,
        unique_id="my_unique_button",
        name="My Button",
    )

    # Assert
    assert button.entity_id.startswith("button.")
    assert "my_unique_button" in button.entity_id


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_button_press_multiple_times(hass: HomeAssistant, coordinator):
    """Test button can be pressed multiple times."""
    # Arrange
    button = MultiscrapeRefreshButton(
        hass=hass,
        coordinator=coordinator,
        unique_id="test_button",
        name="Test Button",
    )

    press_count = 0

    async def mock_refresh():
        nonlocal press_count
        press_count += 1

    coordinator.async_request_refresh = mock_refresh

    # Act - press button 3 times
    await button.async_press()
    await button.async_press()
    await button.async_press()

    # Assert
    assert press_count == 3
