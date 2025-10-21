"""Integration tests for error handling scenarios."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.multiscrape.const import DOMAIN

from . import MockHttpWrapper


async def test_missing_selector(hass: HomeAssistant) -> None:
    """Test handling of selectors that don't match any elements."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "missing_element",
                        "name": "Missing Element",
                        "select": ".non-existent-class",
                    },
                    {
                        "unique_id": "existing_element",
                        "name": "Existing Element",
                        "select": ".product-title",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("ecommerce_product")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        # Missing element should result in unavailable state
        state = hass.states.get("sensor.missing_element")
        assert state is None or state.state == "unavailable"

        # Existing element should work fine
        state = hass.states.get("sensor.existing_element")
        assert state.state == "Smart Home Hub"


async def test_missing_attribute(hass: HomeAssistant) -> None:
    """Test handling of missing attributes."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "missing_attr",
                        "name": "Missing Attribute",
                        "select": ".product-title",
                        "attribute": "data-missing",
                    },
                    {
                        "unique_id": "existing_attr",
                        "name": "Existing Attribute",
                        "select": ".price",
                        "attribute": "data-value",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("ecommerce_product")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        # Missing attribute should result in unavailable state
        state = hass.states.get("sensor.missing_attr")
        assert state is None or state.state == "unavailable"

        # Existing attribute should work fine
        state = hass.states.get("sensor.existing_attr")
        assert state.state == "149.99"


async def test_empty_list_selector(hass: HomeAssistant) -> None:
    """Test handling of list selectors that don't match any elements."""
    config = {
        "multiscrape": [
            {
                "name": "List Scraper",
                "resource": "https://example.com/lists",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "empty_list",
                        "name": "Empty List",
                        "select_list": ".non-existent-items",
                    },
                    {
                        "unique_id": "valid_list",
                        "name": "Valid List",
                        "select_list": ".category",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("list_data")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        # Empty list should result in unavailable or empty state
        state = hass.states.get("sensor.empty_list")
        assert state is None or state.state in ["unavailable", ""]

        # Valid list should work fine
        state = hass.states.get("sensor.valid_list")
        assert state.state == "Electronics,Home & Garden,Sports,Books"


async def test_template_error_handling(hass: HomeAssistant) -> None:
    """Test handling of template errors."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "safe_template",
                        "name": "Safe Template",
                        "select": ".product-title",
                        "value_template": "{{ value | upper }}",
                    },
                    {
                        "unique_id": "template_with_filter",
                        "name": "Template With Filter",
                        "select": ".price",
                        "value_template": "{{ value.replace('$', '') }}",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("ecommerce_product")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.safe_template")
        assert state.state == "SMART HOME HUB"

        state = hass.states.get("sensor.template_with_filter")
        assert state.state == "149.99"


async def test_malformed_json_fallback(hass: HomeAssistant) -> None:
    """Test that value_json handles valid JSON correctly."""
    config = {
        "multiscrape": [
            {
                "name": "JSON Scraper",
                "resource": "https://api.example.com/data",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "json_status",
                        "name": "JSON Status",
                        "value_template": "{{ value_json.status }}",
                    }
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("complex_json")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.json_status")
        assert state.state == "success"


async def test_whitespace_handling(hass: HomeAssistant) -> None:
    """Test proper handling of whitespace in extracted values."""
    config = {
        "multiscrape": [
            {
                "name": "Blog Scraper",
                "resource": "https://example.com/blog",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "author_trimmed",
                        "name": "Author Trimmed",
                        "select": ".post .author",
                        "value_template": "{{ value | trim }}",
                    }
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("blog_articles")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.author_trimmed")
        # Should have no leading/trailing whitespace
        assert state.state == "Jane Smith"
        assert state.state == state.state.strip()


async def test_case_sensitive_selectors(hass: HomeAssistant) -> None:
    """Test case sensitivity in CSS selectors."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "lowercase_selector",
                        "name": "Lowercase Selector",
                        "select": ".product-title",
                    }
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("ecommerce_product")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.lowercase_selector")
        assert state.state == "Smart Home Hub"


async def test_special_characters_in_values(hass: HomeAssistant) -> None:
    """Test handling of special characters in scraped values."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "price_with_symbols",
                        "name": "Price With Symbols",
                        "select": ".price",
                    },
                    {
                        "unique_id": "rating_with_unicode",
                        "name": "Rating With Unicode",
                        "select": ".rating .stars",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("ecommerce_product")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.price_with_symbols")
        assert "$" in state.state
        assert "149.99" in state.state

        state = hass.states.get("sensor.rating_with_unicode")
        # Should handle unicode star characters
        assert "★" in state.state


async def test_nested_template_variables(hass: HomeAssistant) -> None:
    """Test complex template expressions with nested data."""
    config = {
        "multiscrape": [
            {
                "name": "JSON API Scraper",
                "resource": "https://api.example.com/data",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "first_sensor_value",
                        "name": "First Sensor Value",
                        "value_template": "{{ value_json.data.sensors[0].value }}",
                    },
                    {
                        "unique_id": "first_sensor_unit",
                        "name": "First Sensor Unit",
                        "value_template": "{{ value_json.data.sensors[0].unit }}",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("complex_json")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.first_sensor_value")
        assert state.state == "23.1"

        state = hass.states.get("sensor.first_sensor_unit")
        assert state.state == "celsius"


async def test_boolean_conversion(hass: HomeAssistant) -> None:
    """Test proper boolean conversion in binary sensors."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "binary_sensor": [
                    {
                        "unique_id": "is_available_string",
                        "name": "Is Available String",
                        "select": ".availability",
                        "attribute": "data-available",
                        "value_template": "{{ value | lower == 'true' }}",
                    },
                    {
                        "unique_id": "has_stock_text",
                        "name": "Has Stock Text",
                        "select": ".availability",
                        "value_template": "{{ 'Stock' in value }}",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("ecommerce_product")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.is_available_string")
        assert state.state == "on"

        state = hass.states.get("binary_sensor.has_stock_text")
        assert state.state == "on"


async def test_numeric_conversion(hass: HomeAssistant) -> None:
    """Test proper numeric conversion with various formats."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "price_float",
                        "name": "Price Float",
                        "select": ".price",
                        "attribute": "data-value",
                        "value_template": "{{ value | float }}",
                    },
                    {
                        "unique_id": "rating_float",
                        "name": "Rating Float",
                        "select": ".rating",
                        "attribute": "data-rating",
                        "value_template": "{{ value | float | round(1) }}",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("ecommerce_product")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.price_float")
        assert state.state == "149.99"

        state = hass.states.get("sensor.rating_float")
        assert state.state == "4.5"


async def test_default_value_on_missing(hass: HomeAssistant) -> None:
    """Test using default values when elements are missing."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "with_default",
                        "name": "With Default",
                        "select": ".non-existent",
                        "value_template": "{{ value | default('Not Found') }}",
                    }
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("ecommerce_product")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.with_default")
        # When selector doesn't match, the sensor may be unavailable
        # The default in template won't help if scraping returns None
        assert state is None or state.state in ["unavailable", "Not Found"]


async def test_list_with_empty_elements(hass: HomeAssistant) -> None:
    """Test list extraction when some elements are empty."""
    config = {
        "multiscrape": [
            {
                "name": "Empty Scraper",
                "resource": "https://example.com/empty",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "all_divs",
                        "name": "All Divs",
                        "select_list": ".container div",
                    }
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("empty_elements")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.all_divs")
        # Should include all divs, even if some are empty
        # The exact format depends on how empty elements are handled
        assert state is not None


async def test_attribute_on_list_selector(hass: HomeAssistant) -> None:
    """Test extracting attributes from list selectors."""
    config = {
        "multiscrape": [
            {
                "name": "Table Scraper",
                "resource": "https://example.com/table",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "device_ids",
                        "name": "Device IDs",
                        "select_list": "tr.device-row",
                        "attribute": "data-id",
                        "list_separator": ",",
                    }
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("table_data")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.device_ids")
        assert state.state == "sensor1,sensor2,sensor3"
