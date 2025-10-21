"""Comprehensive integration tests for all scraping scenarios."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.multiscrape.const import DOMAIN

from . import MockHttpWrapper


async def test_basic_text_extraction(hass: HomeAssistant) -> None:
    """Test basic text extraction from HTML elements."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "product_title",
                        "name": "Product Title",
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

        state = hass.states.get("sensor.product_title")
        assert state.state == "Smart Home Hub"


async def test_attribute_extraction(hass: HomeAssistant) -> None:
    """Test extraction of HTML attributes."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "product_price_value",
                        "name": "Product Price Value",
                        "select": ".price",
                        "attribute": "data-value",
                    },
                    {
                        "unique_id": "product_rating",
                        "name": "Product Rating",
                        "select": ".rating",
                        "attribute": "data-rating",
                    },
                    {
                        "unique_id": "product_available",
                        "name": "Product Available",
                        "select": ".availability",
                        "attribute": "data-available",
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

        state = hass.states.get("sensor.product_price_value")
        assert state.state == "149.99"

        state = hass.states.get("sensor.product_rating")
        assert state.state == "4.5"

        state = hass.states.get("sensor.product_available")
        assert state.state == "true"


async def test_value_template_processing(hass: HomeAssistant) -> None:
    """Test value templates for post-processing scraped data."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "price_numeric",
                        "name": "Price Numeric",
                        "select": ".price",
                        "value_template": "{{ value.replace('$', '').replace(',', '') | float }}",
                    },
                    {
                        "unique_id": "review_count",
                        "name": "Review Count",
                        "select": ".rating .count",
                        "value_template": "{{ value.strip('()').split()[0] | int }}",
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

        state = hass.states.get("sensor.price_numeric")
        assert state.state == "149.99"

        state = hass.states.get("sensor.review_count")
        assert state.state == "327"


async def test_list_selector(hass: HomeAssistant) -> None:
    """Test list selector to extract multiple elements."""
    config = {
        "multiscrape": [
            {
                "name": "List Scraper",
                "resource": "https://example.com/lists",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "categories",
                        "name": "Categories",
                        "select_list": ".category",
                    },
                    {
                        "unique_id": "prices",
                        "name": "Prices",
                        "select_list": ".price",
                        "list_separator": " | ",
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

        state = hass.states.get("sensor.categories")
        assert state.state == "Electronics,Home & Garden,Sports,Books"

        state = hass.states.get("sensor.prices")
        assert state.state == "$29.99 | $49.99 | $15.50"


async def test_multiple_sensors_same_resource(hass: HomeAssistant) -> None:
    """Test multiple sensors scraping from the same resource."""
    config = {
        "multiscrape": [
            {
                "name": "Weather Scraper",
                "resource": "https://example.com/weather",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "temperature",
                        "name": "Temperature",
                        "select": ".temperature",
                    },
                    {
                        "unique_id": "condition",
                        "name": "Condition",
                        "select": ".condition",
                    },
                    {
                        "unique_id": "humidity",
                        "name": "Humidity",
                        "select": ".humidity span",
                    },
                    {
                        "unique_id": "wind_speed",
                        "name": "Wind Speed",
                        "select": ".wind span",
                        "attribute": "data-speed",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("weather_data")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.temperature")
        assert state.state == "72°F"

        state = hass.states.get("sensor.condition")
        assert state.state == "Partly Cloudy"

        state = hass.states.get("sensor.humidity")
        assert state.state == "65%"

        state = hass.states.get("sensor.wind_speed")
        assert state.state == "12"


async def test_sensor_with_attributes(hass: HomeAssistant) -> None:
    """Test sensors with additional attributes."""
    config = {
        "multiscrape": [
            {
                "name": "Blog Scraper",
                "resource": "https://example.com/blog",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "latest_post",
                        "name": "Latest Post",
                        "select": ".post .post-title",
                        "attributes": [
                            {
                                "name": "author",
                                "select": ".post .author",
                            },
                            {
                                "name": "author_id",
                                "select": ".post .author",
                                "attribute": "data-author-id",
                            },
                            {
                                "name": "published",
                                "select": ".post .published",
                                "attribute": "datetime",
                            },
                            {
                                "name": "read_time",
                                "select": ".post .read-time",
                            },
                        ],
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

        state = hass.states.get("sensor.latest_post")
        assert state.state == "Getting Started with Home Automation"
        assert state.attributes["author"] == "Jane Smith"
        assert state.attributes["author_id"] == "42"
        assert state.attributes["published"] == "2024-01-15T10:30:00Z"
        assert state.attributes["read_time"] == "5 min read"


async def test_json_parsing(hass: HomeAssistant) -> None:
    """Test parsing JSON responses."""
    config = {
        "multiscrape": [
            {
                "name": "JSON API Scraper",
                "resource": "https://api.example.com/data",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "api_temperature",
                        "name": "API Temperature",
                        "value_template": "{{ value_json.data.temperature }}",
                    },
                    {
                        "unique_id": "api_humidity",
                        "name": "API Humidity",
                        "value_template": "{{ value_json.data.humidity }}",
                    },
                    {
                        "unique_id": "api_location",
                        "name": "API Location",
                        "value_template": "{{ value_json.data.metadata.location }}",
                    },
                    {
                        "unique_id": "sensor_count",
                        "name": "Sensor Count",
                        "value_template": "{{ value_json.data.sensors | length }}",
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

        state = hass.states.get("sensor.api_temperature")
        assert state.state == "22.5"

        state = hass.states.get("sensor.api_humidity")
        assert state.state == "65"

        state = hass.states.get("sensor.api_location")
        assert state.state == "Living Room"

        state = hass.states.get("sensor.sensor_count")
        assert state.state == "2"


async def test_xml_parsing(hass: HomeAssistant) -> None:
    """Test parsing XML/RSS feeds."""
    config = {
        "multiscrape": [
            {
                "name": "RSS Feed Scraper",
                "resource": "https://example.com/rss",
                "scan_interval": 3600,
                "parser": "lxml-xml",
                "sensor": [
                    {
                        "unique_id": "feed_title",
                        "name": "Feed Title",
                        "select": "channel > title",
                    },
                    {
                        "unique_id": "latest_item_title",
                        "name": "Latest Item Title",
                        "select": "item > title",
                    },
                    {
                        "unique_id": "latest_item_link",
                        "name": "Latest Item Link",
                        "select": "item > link",
                    },
                    {
                        "unique_id": "latest_item_category",
                        "name": "Latest Item Category",
                        "select": "item > category",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("xml_feed")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.feed_title")
        assert state.state == "Smart Home News"

        state = hass.states.get("sensor.latest_item_title")
        assert state.state == "New Device Release"

        state = hass.states.get("sensor.latest_item_link")
        assert state.state == "https://example.com/article1"

        state = hass.states.get("sensor.latest_item_category")
        assert state.state == "Products"


async def test_table_data_extraction(hass: HomeAssistant) -> None:
    """Test extracting data from HTML tables."""
    config = {
        "multiscrape": [
            {
                "name": "Table Scraper",
                "resource": "https://example.com/table",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "first_device_name",
                        "name": "First Device Name",
                        "select": "tr.device-row:nth-of-type(1) .name",
                    },
                    {
                        "unique_id": "first_device_battery",
                        "name": "First Device Battery",
                        "select": "tr.device-row:nth-of-type(1) .battery",
                    },
                    {
                        "unique_id": "device_count",
                        "name": "Device Count",
                        "select_list": "tr.device-row",
                        "value_template": "{{ value.split(',') | length }}",
                    },
                    {
                        "unique_id": "all_device_names",
                        "name": "All Device Names",
                        "select_list": "tr.device-row .name",
                        "list_separator": ", ",
                    },
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

        state = hass.states.get("sensor.first_device_name")
        assert state.state == "Temperature Sensor"

        state = hass.states.get("sensor.first_device_battery")
        assert state.state == "85%"

        state = hass.states.get("sensor.device_count")
        assert state.state == "3"

        state = hass.states.get("sensor.all_device_names")
        assert state.state == "Temperature Sensor, Motion Detector, Door Sensor"


async def test_nested_selectors(hass: HomeAssistant) -> None:
    """Test deeply nested CSS selectors."""
    config = {
        "multiscrape": [
            {
                "name": "Nested Scraper",
                "resource": "https://example.com/nested",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "nested_title",
                        "name": "Nested Title",
                        "select": ".container .main .wrapper .inner .content header .deep-title",
                    },
                    {
                        "unique_id": "nested_paragraph",
                        "name": "Nested Paragraph",
                        "select": ".content .body .deep-paragraph",
                    },
                    {
                        "unique_id": "author_link",
                        "name": "Author Link",
                        "select": ".content .body .meta .author .author-link",
                        "attribute": "href",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("nested_structure")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.nested_title")
        assert state.state == "Deeply Nested Title"

        state = hass.states.get("sensor.nested_paragraph")
        assert state.state == "This is deeply nested content"

        state = hass.states.get("sensor.author_link")
        assert state.state == "/author/123"


async def test_binary_sensor(hass: HomeAssistant) -> None:
    """Test binary sensor with boolean value templates."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "binary_sensor": [
                    {
                        "unique_id": "in_stock",
                        "name": "In Stock",
                        "select": ".availability",
                        "value_template": "{{ 'In Stock' in value }}",
                    },
                    {
                        "unique_id": "high_rating",
                        "name": "High Rating",
                        "select": ".rating",
                        "attribute": "data-rating",
                        "value_template": "{{ value | float >= 4.0 }}",
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

        state = hass.states.get("binary_sensor.in_stock")
        assert state.state == "on"

        state = hass.states.get("binary_sensor.high_rating")
        assert state.state == "on"


async def test_binary_sensor_with_attributes(hass: HomeAssistant) -> None:
    """Test binary sensor with additional attributes."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "binary_sensor": [
                    {
                        "unique_id": "product_available",
                        "name": "Product Available",
                        "select": ".availability",
                        "value_template": "{{ 'In Stock' in value }}",
                        "attributes": [
                            {
                                "name": "price",
                                "select": ".price",
                            },
                            {
                                "name": "rating",
                                "select": ".rating",
                                "attribute": "data-rating",
                            },
                            {
                                "name": "title",
                                "select": ".product-title",
                            },
                        ],
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

        state = hass.states.get("binary_sensor.product_available")
        assert state.state == "on"
        assert state.attributes["price"] == "$149.99"
        assert state.attributes["rating"] == "4.5"
        assert state.attributes["title"] == "Smart Home Hub"


async def test_list_attributes(hass: HomeAssistant) -> None:
    """Test extracting lists as attributes."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "product_info",
                        "name": "Product Info",
                        "select": ".product-title",
                        "attributes": [
                            {
                                "name": "features",
                                "select_list": ".features li",
                                "list_separator": " | ",
                            }
                        ],
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

        state = hass.states.get("sensor.product_info")
        assert state.state == "Smart Home Hub"
        assert (
            state.attributes["features"]
            == "WiFi 6 support | Zigbee compatible | Voice assistant integration"
        )


async def test_complex_value_templates(hass: HomeAssistant) -> None:
    """Test complex Jinja2 value templates."""
    config = {
        "multiscrape": [
            {
                "name": "Blog Scraper",
                "resource": "https://example.com/blog",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "tags_formatted",
                        "name": "Tags Formatted",
                        "select_list": ".post .tags .tag",
                        "value_template": "{{ value.split(',') | map('trim') | map('upper') | join(' | ') }}",
                    },
                    {
                        "unique_id": "published_date_formatted",
                        "name": "Published Date Formatted",
                        "select": ".post .published",
                        "attribute": "datetime",
                        "value_template": "{{ value.split('T')[0] }}",
                    },
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

        state = hass.states.get("sensor.tags_formatted")
        assert state.state == "AUTOMATION | SMART-HOME | IOT"

        state = hass.states.get("sensor.published_date_formatted")
        assert state.state == "2024-01-15"


async def test_news_list_extraction(hass: HomeAssistant) -> None:
    """Test extracting news headlines and links."""
    config = {
        "multiscrape": [
            {
                "name": "News Scraper",
                "resource": "https://example.com/news",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "featured_headline",
                        "name": "Featured Headline",
                        "select": ".headline.featured .title",
                    },
                    {
                        "unique_id": "featured_category",
                        "name": "Featured Category",
                        "select": ".headline.featured .category",
                    },
                    {
                        "unique_id": "featured_link",
                        "name": "Featured Link",
                        "select": ".headline.featured .link",
                        "attribute": "href",
                    },
                    {
                        "unique_id": "news_headlines",
                        "name": "News Headlines",
                        "select_list": ".news-list .news-item a",
                        "list_separator": " || ",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("news_feed")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.featured_headline")
        assert state.state == "Major Technology Breakthrough"

        state = hass.states.get("sensor.featured_category")
        assert state.state == "Technology"

        state = hass.states.get("sensor.featured_link")
        assert state.state == "/news/article-1"

        state = hass.states.get("sensor.news_headlines")
        assert (
            "Smart Home Market Growth" in state.state
            and "New IoT Security Standards" in state.state
            and "AI Integration Updates" in state.state
        )


async def test_empty_element_handling(hass: HomeAssistant) -> None:
    """Test handling of empty and missing elements."""
    config = {
        "multiscrape": [
            {
                "name": "Empty Scraper",
                "resource": "https://example.com/empty",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "valid_content",
                        "name": "Valid Content",
                        "select": ".valid",
                    },
                    {
                        "unique_id": "empty_text",
                        "name": "Empty Text",
                        "select": ".empty-text",
                    },
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

        state = hass.states.get("sensor.valid_content")
        assert state.state == "Valid Content"

        state = hass.states.get("sensor.empty_text")
        # Empty elements should result in unavailable or empty string
        assert state is None or state.state == "" or state.state == "unavailable"


async def test_weather_forecast_extraction(hass: HomeAssistant) -> None:
    """Test extracting weather forecast data."""
    config = {
        "multiscrape": [
            {
                "name": "Weather Scraper",
                "resource": "https://example.com/weather",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "current_temp",
                        "name": "Current Temperature",
                        "select": ".weather-widget .current .temperature",
                    },
                    {
                        "unique_id": "temp_celsius",
                        "name": "Temperature Celsius",
                        "select": ".weather-widget .current .temperature",
                        "attribute": "data-celsius",
                    },
                    {
                        "unique_id": "forecast_days",
                        "name": "Forecast Days",
                        "select_list": ".forecast .day .day-name",
                        "list_separator": ", ",
                    },
                    {
                        "unique_id": "forecast_highs",
                        "name": "Forecast Highs",
                        "select_list": ".forecast .day .high",
                        "list_separator": " / ",
                    },
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("weather_data")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.current_temp")
        assert state.state == "72°F"

        state = hass.states.get("sensor.temp_celsius")
        assert state.state == "22"

        state = hass.states.get("sensor.forecast_days")
        assert state.state == "Monday, Tuesday"

        state = hass.states.get("sensor.forecast_highs")
        assert state.state == "75°F / 78°F"
