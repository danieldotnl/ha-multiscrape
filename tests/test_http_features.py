"""Integration tests for HTTP features and error handling."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.multiscrape.const import DOMAIN

from . import MockHttpWrapper


async def test_post_request(hass: HomeAssistant) -> None:
    """Test POST request with payload."""
    config = {
        "multiscrape": [
            {
                "name": "API Scraper",
                "resource": "https://api.example.com/data",
                "method": "POST",
                "payload": '{"query": "temperature"}',
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "api_temp",
                        "name": "API Temperature",
                        "value_template": "{{ value_json.data.temperature }}",
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

        state = hass.states.get("sensor.api_temperature")
        assert state.state == "22.5"


async def test_headers_configuration(hass: HomeAssistant) -> None:
    """Test custom headers in requests."""
    config = {
        "multiscrape": [
            {
                "name": "API Scraper",
                "resource": "https://api.example.com/data",
                "headers": {
                    "User-Agent": "HomeAssistant/1.0",
                    "Accept": "application/json",
                },
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "api_humidity",
                        "name": "API Humidity",
                        "value_template": "{{ value_json.data.humidity }}",
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

        state = hass.states.get("sensor.api_humidity")
        assert state.state == "65"


async def test_authentication_basic(hass: HomeAssistant) -> None:
    """Test basic authentication."""
    config = {
        "multiscrape": [
            {
                "name": "Protected Scraper",
                "resource": "https://example.com/protected",
                "username": "testuser",
                "password": "testpass",
                "authentication": "basic",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "total_devices",
                        "name": "Total Devices",
                        "select": ".stat .value",
                    }
                ],
            }
        ]
    }

    mocker = MockHttpWrapper("authenticated_content")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.total_devices")
        assert state.state == "24"


async def test_url_parameters(hass: HomeAssistant) -> None:
    """Test URL parameters configuration."""
    config = {
        "multiscrape": [
            {
                "name": "API Scraper",
                "resource": "https://api.example.com/data",
                "params": {
                    "format": "json",
                    "units": "metric",
                },
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "api_status",
                        "name": "API Status",
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

        state = hass.states.get("sensor.api_status")
        assert state.state == "success"


async def test_multiple_configurations(hass: HomeAssistant) -> None:
    """Test multiple scraper configurations in one setup."""
    config = {
        "multiscrape": [
            {
                "name": "Weather Scraper",
                "resource": "https://example.com/weather",
                "scan_interval": 1800,
                "sensor": [
                    {
                        "unique_id": "weather_temp",
                        "name": "Weather Temperature",
                        "select": ".temperature",
                    }
                ],
            },
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "product_price",
                        "name": "Product Price",
                        "select": ".price",
                    }
                ],
            },
            {
                "name": "News Scraper",
                "resource": "https://example.com/news",
                "scan_interval": 900,
                "sensor": [
                    {
                        "unique_id": "news_headline",
                        "name": "News Headline",
                        "select": ".headline .title",
                    }
                ],
            },
        ]
    }

    # Use a custom mocker that can handle multiple test names
    class MultiMockHttpWrapper:
        def __init__(self):
            self.count = 0

        async def async_request(
            self, context, resource, method=None, request_data=None, cookies=None, variables: dict = {}
        ):
            self.count += 1
            if "weather" in resource:
                return (await MockHttpWrapper("weather_data").async_request(
                    context, resource, method, request_data, cookies, variables
                ))
            elif "product" in resource:
                return (await MockHttpWrapper("ecommerce_product").async_request(
                    context, resource, method, request_data, cookies, variables
                ))
            elif "news" in resource:
                return (await MockHttpWrapper("news_feed").async_request(
                    context, resource, method, request_data, cookies, variables
                ))

    mocker = MultiMockHttpWrapper()
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.weather_temperature")
        assert state.state == "72°F"

        state = hass.states.get("sensor.product_price")
        assert state.state == "$149.99"

        state = hass.states.get("sensor.news_headline")
        assert state.state == "Major Technology Breakthrough"


async def test_icon_template(hass: HomeAssistant) -> None:
    """Test dynamic icon templates based on sensor value."""
    config = {
        "multiscrape": [
            {
                "name": "Weather Scraper",
                "resource": "https://example.com/weather",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "weather_condition",
                        "name": "Weather Condition",
                        "select": ".condition",
                        "icon": "{% if 'Cloudy' in value %}mdi:weather-cloudy{% else %}mdi:weather-sunny{% endif %}",
                    }
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

        state = hass.states.get("sensor.weather_condition")
        assert state.state == "Partly Cloudy"
        assert state.attributes.get("icon") == "mdi:weather-cloudy"


async def test_device_class_and_unit(hass: HomeAssistant) -> None:
    """Test sensor device class and unit of measurement."""
    config = {
        "multiscrape": [
            {
                "name": "Weather Scraper",
                "resource": "https://example.com/weather",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "temperature_numeric",
                        "name": "Temperature Numeric",
                        "select": ".temperature",
                        "attribute": "data-celsius",
                        "device_class": "temperature",
                        "unit_of_measurement": "°C",
                        "state_class": "measurement",
                    },
                    {
                        "unique_id": "humidity_numeric",
                        "name": "Humidity Numeric",
                        "select": ".humidity span",
                        "value_template": "{{ value.strip('%') | int }}",
                        "device_class": "humidity",
                        "unit_of_measurement": "%",
                        "state_class": "measurement",
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

        state = hass.states.get("sensor.temperature_numeric")
        assert state.state == "22"
        assert state.attributes.get("device_class") == "temperature"
        assert state.attributes.get("unit_of_measurement") == "°C"

        state = hass.states.get("sensor.humidity_numeric")
        assert state.state == "65"
        assert state.attributes.get("device_class") == "humidity"
        assert state.attributes.get("unit_of_measurement") == "%"


async def test_content_and_tag_extraction(hass: HomeAssistant) -> None:
    """Test content (inner HTML) and tag (full HTML) extraction."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "description_content",
                        "name": "Description Content",
                        "select": ".description",
                        "extract": "content",
                    },
                    {
                        "unique_id": "price_tag",
                        "name": "Price Tag",
                        "select": ".price-container",
                        "extract": "tag",
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

        state = hass.states.get("sensor.description_content")
        # Content extraction should return inner HTML
        assert "<p>" in state.state
        assert "Advanced smart home hub" in state.state

        state = hass.states.get("sensor.price_tag")
        # Tag extraction should return full HTML including the container
        assert "price-container" in state.state
        assert "$149.99" in state.state


async def test_link_extraction(hass: HomeAssistant) -> None:
    """Test extraction of links from various elements."""
    config = {
        "multiscrape": [
            {
                "name": "Product Scraper",
                "resource": "https://example.com/product",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "product_link",
                        "name": "Product Link",
                        "select": ".buy-button",
                        "attribute": "href",
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

        state = hass.states.get("sensor.product_link")
        assert state.state == "/product/12345"


async def test_combined_text_and_attribute(hass: HomeAssistant) -> None:
    """Test combining text content with attribute values."""
    config = {
        "multiscrape": [
            {
                "name": "Blog Scraper",
                "resource": "https://example.com/blog",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "article_with_meta",
                        "name": "Article With Meta",
                        "select": ".post .post-title",
                        "attributes": [
                            {
                                "name": "url_text",
                                "select": ".post .post-title",
                            },
                            {
                                "name": "author",
                                "select": ".post .author",
                            },
                            {
                                "name": "author_id",
                                "select": ".post .author",
                                "attribute": "data-author-id",
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

        state = hass.states.get("sensor.article_with_meta")
        assert state.state == "Getting Started with Home Automation"
        assert state.attributes["url_text"] == "Getting Started with Home Automation"
        assert state.attributes["author"] == "Jane Smith"
        assert state.attributes["author_id"] == "42"


async def test_nth_child_selectors(hass: HomeAssistant) -> None:
    """Test nth-child and nth-of-type selectors."""
    config = {
        "multiscrape": [
            {
                "name": "Blog Scraper",
                "resource": "https://example.com/blog",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "first_post_title",
                        "name": "First Post Title",
                        "select": "article.post:nth-of-type(1) .post-title",
                    },
                    {
                        "unique_id": "second_post_title",
                        "name": "Second Post Title",
                        "select": "article.post:nth-of-type(2) .post-title",
                    },
                    {
                        "unique_id": "second_post_author",
                        "name": "Second Post Author",
                        "select": "article.post:nth-of-type(2) .author",
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

        state = hass.states.get("sensor.first_post_title")
        assert state.state == "Getting Started with Home Automation"

        state = hass.states.get("sensor.second_post_title")
        assert state.state == "Advanced Sensor Integration"

        state = hass.states.get("sensor.second_post_author")
        assert state.state == "John Doe"


async def test_image_attribute_extraction(hass: HomeAssistant) -> None:
    """Test extraction of image attributes."""
    config = {
        "multiscrape": [
            {
                "name": "Weather Scraper",
                "resource": "https://example.com/weather",
                "scan_interval": 3600,
                "sensor": [
                    {
                        "unique_id": "weather_icon_url",
                        "name": "Weather Icon URL",
                        "select": ".weather-widget .icon",
                        "attribute": "src",
                    },
                    {
                        "unique_id": "weather_icon_alt",
                        "name": "Weather Icon Alt",
                        "select": ".weather-widget .icon",
                        "attribute": "alt",
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

        state = hass.states.get("sensor.weather_icon_url")
        assert state.state == "/icons/partly-cloudy.png"

        state = hass.states.get("sensor.weather_icon_alt")
        assert state.state == "weather icon"
