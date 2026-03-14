"""Tests for the ScraperRegistry."""

from unittest.mock import MagicMock

import pytest
from homeassistant.const import Platform

from custom_components.multiscrape.registry import (ScraperInstance,
                                                    ScraperRegistry)


@pytest.fixture
def registry():
    """Create a fresh ScraperRegistry."""
    return ScraperRegistry()


@pytest.fixture
def make_instance():
    """Create ScraperInstance objects for testing."""
    def _make(scraper_id="test_scraper", platform_configs=None):
        return ScraperInstance(
            scraper_id=scraper_id,
            scraper=MagicMock(),
            coordinator=MagicMock(),
            platform_configs=platform_configs or {},
        )
    return _make


def test_register_and_get(registry, make_instance):
    """Test registering and retrieving a scraper instance."""
    instance = make_instance("my_scraper")
    registry.register(instance)
    assert registry.get("my_scraper") is instance


def test_get_missing_raises_key_error(registry):
    """Test that getting a missing scraper raises KeyError."""
    with pytest.raises(KeyError):
        registry.get("nonexistent")


def test_register_duplicate_raises_value_error(registry, make_instance):
    """Test that registering a duplicate ID raises ValueError."""
    registry.register(make_instance("dup"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(make_instance("dup"))


def test_get_all(registry, make_instance):
    """Test get_all returns all registered instances."""
    a = make_instance("a")
    b = make_instance("b")
    registry.register(a)
    registry.register(b)

    result = registry.get_all()
    assert len(result) == 2
    assert a in result
    assert b in result


def test_get_all_empty(registry):
    """Test get_all on empty registry returns empty list."""
    assert registry.get_all() == []


def test_clear(registry, make_instance):
    """Test clear removes all registered instances."""
    registry.register(make_instance("a"))
    registry.register(make_instance("b"))
    registry.clear()
    assert registry.get_all() == []


def test_platform_configs_access(registry, make_instance):
    """Test accessing platform configs through the instance."""
    sensor_config = {"name": "temp_sensor", "select": ".temp"}
    instance = make_instance(
        "my_scraper",
        platform_configs={
            Platform.SENSOR: {"temp_sensor": sensor_config},
        },
    )
    registry.register(instance)

    retrieved = registry.get("my_scraper")
    assert retrieved.platform_configs[Platform.SENSOR]["temp_sensor"] is sensor_config


def test_contains(registry, make_instance):
    """Test contains checks for registered IDs."""
    assert registry.contains("my_scraper") is False
    registry.register(make_instance("my_scraper"))
    assert registry.contains("my_scraper") is True
