"""Tests for XML scraping with the lxml-xml parser.

These tests verify that the multiscrape component correctly handles XML content
when configured with the 'lxml-xml' parser, including:
- RSS/Atom feeds
- Weather data
- SOAP responses
- XML with attributes
- XML with CDATA sections
- XML with namespaces
- XML with select_list
- XML with value_template
- Error handling for malformed XML
"""


import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import DEFAULT_SEPARATOR
from custom_components.multiscrape.scrape_context import ScrapeContext
from custom_components.multiscrape.scraper import Scraper
from custom_components.multiscrape.selector import Selector

from .fixtures.xml_samples import (SAMPLE_XML_ATTRIBUTES, SAMPLE_XML_CDATA,
                                   SAMPLE_XML_EMPTY, SAMPLE_XML_HTML_TAG_NAMES,
                                   SAMPLE_XML_MALFORMED, SAMPLE_XML_NAMESPACES,
                                   SAMPLE_XML_RSS, SAMPLE_XML_SOAP,
                                   SAMPLE_XML_WEATHER)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def xml_scraper(hass: HomeAssistant):
    """Create a Scraper configured for XML parsing (lxml-xml)."""
    return Scraper("test_xml_scraper", hass, None, "lxml-xml", DEFAULT_SEPARATOR)


@pytest.fixture
def xml_scraper_custom_separator(hass: HomeAssistant):
    """Create a Scraper configured for XML parsing with custom separator."""
    return Scraper("test_xml_scraper", hass, None, "lxml-xml", " | ")


# ============================================================================
# Basic XML Parsing Tests
# ============================================================================


class TestXmlBasicParsing:
    """Test basic XML content is correctly parsed with lxml-xml parser."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_content_is_parsed_to_soup(self, hass: HomeAssistant, xml_scraper):
        """Test that XML content is parsed into a BeautifulSoup object."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        assert xml_scraper._soup is not None
        assert xml_scraper._data == SAMPLE_XML_WEATHER
        assert xml_scraper._is_json is False

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_empty_document_is_parsed(self, hass: HomeAssistant, xml_scraper):
        """Test that an empty XML root element is parsed without error."""
        await xml_scraper.set_content(SAMPLE_XML_EMPTY)

        assert xml_scraper._soup is not None

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_formatted_content_is_prettified(self, hass: HomeAssistant, xml_scraper):
        """Test that formatted_content returns prettified XML."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        formatted = xml_scraper.formatted_content
        assert "\n" in formatted
        assert "temperature" in formatted


# ============================================================================
# RSS Feed Scraping Tests
# ============================================================================


class TestXmlRssScraping:
    """Test scraping RSS feed XML content."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_rss_channel_title(self, hass: HomeAssistant, xml_scraper):
        """Test extracting the channel title from an RSS feed."""
        await xml_scraper.set_content(SAMPLE_XML_RSS)

        selector = Selector(hass, {"select": Template("title", hass)})
        value = xml_scraper.scrape(selector, "rss_title")

        assert value == "Home Assistant Blog"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_rss_first_item_title(self, hass: HomeAssistant, xml_scraper):
        """Test extracting the first item title from an RSS feed."""
        await xml_scraper.set_content(SAMPLE_XML_RSS)

        selector = Selector(hass, {"select": Template("item title", hass)})
        value = xml_scraper.scrape(selector, "rss_item_title")

        assert value == "Release 2024.8"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_rss_item_link(self, hass: HomeAssistant, xml_scraper):
        """Test extracting a link from an RSS item."""
        await xml_scraper.set_content(SAMPLE_XML_RSS)

        selector = Selector(hass, {"select": Template("item link", hass)})
        value = xml_scraper.scrape(selector, "rss_link")

        assert value == "https://www.home-assistant.io/blog/2024/08/release"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_rss_all_item_titles_with_select_list(
        self, hass: HomeAssistant, xml_scraper
    ):
        """Test extracting all item titles using select_list."""
        await xml_scraper.set_content(SAMPLE_XML_RSS)

        selector = Selector(hass, {"select_list": Template("item title", hass)})
        value = xml_scraper.scrape(selector, "rss_titles")

        assert value == "Release 2024.8,Release 2024.7"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_rss_pubdate(self, hass: HomeAssistant, xml_scraper):
        """Test extracting pubDate from RSS feed."""
        await xml_scraper.set_content(SAMPLE_XML_RSS)

        selector = Selector(hass, {"select": Template("item pubDate", hass)})
        value = xml_scraper.scrape(selector, "rss_date")

        assert "Wed, 07 Aug 2024" in value


# ============================================================================
# Weather XML Scraping Tests
# ============================================================================


class TestXmlWeatherScraping:
    """Test scraping weather data from XML."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_temperature(self, hass: HomeAssistant, xml_scraper):
        """Test extracting temperature value from weather XML."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {"select": Template("temperature", hass)})
        value = xml_scraper.scrape(selector, "temperature")

        assert value == "21.5"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_temperature_unit_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting an attribute from an XML element."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("temperature", hass),
            "attribute": "unit",
        })
        value = xml_scraper.scrape(selector, "temp_unit")

        assert value == "celsius"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_wind_speed_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting wind speed attribute from XML."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("wind", hass),
            "attribute": "speed",
        })
        value = xml_scraper.scrape(selector, "wind_speed")

        assert value == "12.3"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_wind_direction_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting wind direction attribute from XML."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("wind", hass),
            "attribute": "direction",
        })
        value = xml_scraper.scrape(selector, "wind_direction")

        assert value == "NW"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_location_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting attributes from self-closing XML tags."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("location", hass),
            "attribute": "city",
        })
        value = xml_scraper.scrape(selector, "city")

        assert value == "Amsterdam"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_condition(self, hass: HomeAssistant, xml_scraper):
        """Test extracting text from nested XML element."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {"select": Template("current condition", hass)})
        value = xml_scraper.scrape(selector, "condition")

        assert value == "Partly Cloudy"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_forecast_days_with_select_list(
        self, hass: HomeAssistant, xml_scraper
    ):
        """Test extracting multiple forecast high values using select_list."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {"select_list": Template("forecast day high", hass)})
        value = xml_scraper.scrape(selector, "forecast_highs")

        assert value == "24.0,22.0"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_forecast_day_date_attributes(
        self, hass: HomeAssistant, xml_scraper
    ):
        """Test extracting date attributes from multiple forecast days."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select_list": Template("forecast day", hass),
            "attribute": "date",
        })
        value = xml_scraper.scrape(selector, "forecast_dates")

        assert value == "2024-08-08,2024-08-09"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_with_value_template(self, hass: HomeAssistant, xml_scraper):
        """Test value_template applied to scraped XML value."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("temperature", hass),
            "value_template": Template("{{ value | float + 5 }}", hass),
        })
        value = xml_scraper.scrape(selector, "temp_adjusted")

        assert float(value) == 26.5

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_humidity_with_value_template(self, hass: HomeAssistant, xml_scraper):
        """Test value_template that formats humidity string."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("humidity", hass),
            "value_template": Template("{{ value }}%", hass),
        })
        value = xml_scraper.scrape(selector, "humidity")

        assert value == "65%"


# ============================================================================
# XML Attribute Extraction Tests
# ============================================================================


class TestXmlAttributeExtraction:
    """Test extracting attributes from XML elements."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_device_id_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting id attribute from a device element."""
        await xml_scraper.set_content(SAMPLE_XML_ATTRIBUTES)

        selector = Selector(hass, {
            "select": Template("device", hass),
            "attribute": "id",
        })
        value = xml_scraper.scrape(selector, "device_id")

        assert value == "light-1"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_device_type_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting type attribute from a device element."""
        await xml_scraper.set_content(SAMPLE_XML_ATTRIBUTES)

        selector = Selector(hass, {
            "select": Template("device", hass),
            "attribute": "type",
        })
        value = xml_scraper.scrape(selector, "device_type")

        assert value == "light"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_all_device_ids_with_select_list(
        self, hass: HomeAssistant, xml_scraper
    ):
        """Test extracting all device id attributes using select_list."""
        await xml_scraper.set_content(SAMPLE_XML_ATTRIBUTES)

        selector = Selector(hass, {
            "select_list": Template("device", hass),
            "attribute": "id",
        })
        value = xml_scraper.scrape(selector, "all_device_ids")

        assert value == "light-1,thermostat-1,sensor-1"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_all_device_rooms_with_select_list(
        self, hass: HomeAssistant, xml_scraper
    ):
        """Test extracting room attributes from all devices."""
        await xml_scraper.set_content(SAMPLE_XML_ATTRIBUTES)

        selector = Selector(hass, {
            "select_list": Template("device", hass),
            "attribute": "room",
        })
        value = xml_scraper.scrape(selector, "all_rooms")

        assert value == "living_room,bedroom,kitchen"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_thermostat_target_temp(self, hass: HomeAssistant, xml_scraper):
        """Test extracting text from a specific nested element."""
        await xml_scraper.set_content(SAMPLE_XML_ATTRIBUTES)

        selector = Selector(hass, {
            "select": Template("device[type='climate'] target_temp", hass),
        })
        value = xml_scraper.scrape(selector, "target_temp")

        assert value == "21.0"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_all_device_names_with_custom_separator(
        self, hass: HomeAssistant, xml_scraper_custom_separator
    ):
        """Test select_list with a custom list separator."""
        await xml_scraper_custom_separator.set_content(SAMPLE_XML_ATTRIBUTES)

        selector = Selector(hass, {"select_list": Template("device name", hass)})
        value = xml_scraper_custom_separator.scrape(selector, "all_names")

        assert value == "Living Room Light | Bedroom Thermostat | Kitchen Humidity"


# ============================================================================
# CDATA Section Tests
# ============================================================================


class TestXmlCdataScraping:
    """Test scraping XML content with CDATA sections."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_cdata_message(self, hass: HomeAssistant, xml_scraper):
        """Test extracting text from CDATA section."""
        await xml_scraper.set_content(SAMPLE_XML_CDATA)

        selector = Selector(hass, {"select": Template("notification message", hass)})
        value = xml_scraper.scrape(selector, "message")

        assert "Motion detected" in value
        assert "<front door>" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_cdata_notification_id_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting attribute from element containing CDATA."""
        await xml_scraper.set_content(SAMPLE_XML_CDATA)

        selector = Selector(hass, {
            "select": Template("notification", hass),
            "attribute": "id",
        })
        value = xml_scraper.scrape(selector, "notif_id")

        assert value == "1"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_cdata_priority_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting priority attribute from notification."""
        await xml_scraper.set_content(SAMPLE_XML_CDATA)

        selector = Selector(hass, {
            "select": Template("notification", hass),
            "attribute": "priority",
        })
        value = xml_scraper.scrape(selector, "priority")

        assert value == "high"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_all_notification_titles(self, hass: HomeAssistant, xml_scraper):
        """Test extracting all notification titles."""
        await xml_scraper.set_content(SAMPLE_XML_CDATA)

        selector = Selector(hass, {"select_list": Template("notification title", hass)})
        value = xml_scraper.scrape(selector, "all_titles")

        assert value == "Security Alert,Update Available"


# ============================================================================
# Extract Mode Tests (text/content/tag)
# ============================================================================


class TestXmlExtractModes:
    """Test the extract parameter with XML content."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_extract_text_from_xml(self, hass: HomeAssistant, xml_scraper):
        """Test extract='text' returns just the text content."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("current", hass),
            "extract": "text",
        })
        value = xml_scraper.scrape(selector, "current_text")

        # Should contain all text nodes within <current>
        assert "21.5" in value
        assert "65" in value
        assert "Partly Cloudy" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_extract_content_from_xml(self, hass: HomeAssistant, xml_scraper):
        """Test extract='content' returns inner XML content."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("current", hass),
            "extract": "content",
        })
        value = xml_scraper.scrape(selector, "current_content")

        # Should contain child tags as strings
        assert "<temperature" in value
        assert "<humidity" in value
        assert "<condition>" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_extract_tag_from_xml(self, hass: HomeAssistant, xml_scraper):
        """Test extract='tag' returns the full XML element including outer tag."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("temperature", hass),
            "extract": "tag",
        })
        value = xml_scraper.scrape(selector, "temp_tag")

        # Should contain the outer <temperature> tag
        assert "<temperature" in value
        assert "</temperature>" in value
        assert "21.5" in value
        assert 'unit="celsius"' in value


# ============================================================================
# Value Template with XML
# ============================================================================


class TestXmlValueTemplate:
    """Test value_template integration with XML scraping."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_value_template_arithmetic(self, hass: HomeAssistant, xml_scraper):
        """Test value_template performing arithmetic on scraped XML value."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("temperature", hass),
            "value_template": Template("{{ (value | float * 9/5) + 32 }}", hass),
        })
        value = xml_scraper.scrape(selector, "temp_fahrenheit")

        # 21.5 * 9/5 + 32 = 70.7
        assert abs(float(value) - 70.7) < 0.01

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_value_template_string_manipulation(self, hass: HomeAssistant, xml_scraper):
        """Test value_template with string operations on XML value."""
        await xml_scraper.set_content(SAMPLE_XML_RSS)

        selector = Selector(hass, {
            "select": Template("item title", hass),
            "value_template": Template("{{ value.replace('Release ', '') }}", hass),
        })
        value = xml_scraper.scrape(selector, "version")

        # HA template engine may parse "2024.8" as a float
        assert str(value) == "2024.8"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_value_template_with_form_variables(self, hass: HomeAssistant, xml_scraper):
        """Test value_template using form variables with XML content."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "select": Template("temperature", hass),
            "value_template": Template("{{ value }}°C (station: {{ station }})", hass),
        })
        ctx = ScrapeContext(form_variables={"station": "AMS-01"})
        value = xml_scraper.scrape(selector, "annotated_temp", context=ctx)

        assert value == "21.5°C (station: AMS-01)"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_value_template_only_no_selector(self, hass: HomeAssistant, xml_scraper):
        """Test value_template without selector (just_value) processes raw XML data."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {
            "value_template": Template("{{ value[:5] }}", hass),
        })
        value = xml_scraper.scrape(selector, "raw_prefix")

        assert value == "<?xml"


# ============================================================================
# Namespace Handling Tests
# ============================================================================


class TestXmlNamespaces:
    """Test scraping XML with namespaces."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_atom_feed_title(self, hass: HomeAssistant, xml_scraper):
        """Test scraping title from an Atom feed with default namespace."""
        await xml_scraper.set_content(SAMPLE_XML_NAMESPACES)

        selector = Selector(hass, {"select": Template("title", hass)})
        value = xml_scraper.scrape(selector, "feed_title")

        assert value == "Smart Home Feed"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_atom_entry_title(self, hass: HomeAssistant, xml_scraper):
        """Test scraping first entry title from Atom feed."""
        await xml_scraper.set_content(SAMPLE_XML_NAMESPACES)

        selector = Selector(hass, {"select": Template("entry title", hass)})
        value = xml_scraper.scrape(selector, "entry_title")

        assert value == "Door Opened"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_atom_entry_content(self, hass: HomeAssistant, xml_scraper):
        """Test scraping content from Atom feed entry."""
        await xml_scraper.set_content(SAMPLE_XML_NAMESPACES)

        selector = Selector(hass, {"select": Template("entry content", hass)})
        value = xml_scraper.scrape(selector, "entry_content")

        assert value == "Front door was opened"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_all_entry_titles(self, hass: HomeAssistant, xml_scraper):
        """Test scraping all entry titles from namespaced feed."""
        await xml_scraper.set_content(SAMPLE_XML_NAMESPACES)

        selector = Selector(hass, {"select_list": Template("entry title", hass)})
        value = xml_scraper.scrape(selector, "all_titles")

        assert value == "Door Opened,Temperature High"


# ============================================================================
# SOAP XML Tests
# ============================================================================


class TestXmlSoapScraping:
    """Test scraping SOAP-style XML responses."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_soap_sensor_value(self, hass: HomeAssistant, xml_scraper):
        """Test extracting a sensor value from SOAP response."""
        await xml_scraper.set_content(SAMPLE_XML_SOAP)

        # lxml-xml handles namespaced tags; try selecting by local name
        selector = Selector(hass, {"select": Template("Value", hass)})
        value = xml_scraper.scrape(selector, "sensor_value")

        assert value == "42.7"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_soap_sensor_unit(self, hass: HomeAssistant, xml_scraper):
        """Test extracting unit from SOAP response."""
        await xml_scraper.set_content(SAMPLE_XML_SOAP)

        selector = Selector(hass, {"select": Template("Unit", hass)})
        value = xml_scraper.scrape(selector, "sensor_unit")

        assert value == "°C"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_soap_all_values_with_select_list(
        self, hass: HomeAssistant, xml_scraper
    ):
        """Test extracting all sensor values from SOAP response."""
        await xml_scraper.set_content(SAMPLE_XML_SOAP)

        selector = Selector(hass, {"select_list": Template("Value", hass)})
        value = xml_scraper.scrape(selector, "all_values")

        assert value == "42.7,1013.25"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_soap_sensor_id_attribute(self, hass: HomeAssistant, xml_scraper):
        """Test extracting id attribute from namespaced element."""
        await xml_scraper.set_content(SAMPLE_XML_SOAP)

        selector = Selector(hass, {
            "select": Template("SensorReading", hass),
            "attribute": "id",
        })
        value = xml_scraper.scrape(selector, "reading_id")

        assert value == "sensor-001"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_scrape_soap_status(self, hass: HomeAssistant, xml_scraper):
        """Test extracting status from SOAP response."""
        await xml_scraper.set_content(SAMPLE_XML_SOAP)

        selector = Selector(hass, {"select": Template("Status", hass)})
        value = xml_scraper.scrape(selector, "sensor_status")

        assert value == "active"


# ============================================================================
# HTML-Colliding Tag Name Tests (template/script/style)
# ============================================================================


class TestXmlHtmlCollidingTagNames:
    """Test that XML tags named 'template', 'script', or 'style' are handled correctly.

    These tag names have special handling in HTML mode (they contain raw text).
    In XML mode, they are ordinary elements with child tags, and the extract
    parameter must be respected — not short-circuited.
    """

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_template_tag_text_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test that a <template> XML element returns text from all children."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("template", hass),
            "extract": "text",
        })
        value = xml_scraper.scrape(selector, "template_text")

        # Should contain text from all child elements, not empty string
        assert "sensor.temperature" in value
        assert "light.turn_on" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_template_tag_content_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test extract='content' on an XML <template> element returns inner XML."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("template", hass),
            "extract": "content",
        })
        value = xml_scraper.scrape(selector, "template_content")

        # Must contain child tags as strings — NOT empty string
        assert "<trigger" in value
        assert "<action" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_template_tag_tag_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test extract='tag' on an XML <template> element returns full outer XML."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("template", hass),
            "extract": "tag",
        })
        value = xml_scraper.scrape(selector, "template_tag")

        # Must include the <template> wrapper tag itself
        assert "<template>" in value
        assert "</template>" in value
        assert "<trigger" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_script_tag_text_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test that a <script> XML element returns text from all children."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("script", hass),
            "extract": "text",
        })
        value = xml_scraper.scrape(selector, "script_text")

        assert "Open blinds" in value
        assert "Turn on coffee maker" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_script_tag_content_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test extract='content' on an XML <script> element returns inner XML."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("script", hass),
            "extract": "content",
        })
        value = xml_scraper.scrape(selector, "script_content")

        assert "<step" in value
        assert "Open blinds" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_script_tag_attribute_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test extracting an attribute from an XML <script> element."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("script", hass),
            "attribute": "id",
        })
        value = xml_scraper.scrape(selector, "script_id")

        assert value == "morning_routine"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_style_tag_text_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test that a <style> XML element returns text from all children."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("style", hass),
            "extract": "text",
        })
        value = xml_scraper.scrape(selector, "style_text")

        assert "black" in value
        assert "white" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_style_tag_content_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test extract='content' on an XML <style> element returns inner XML."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("style", hass),
            "extract": "content",
        })
        value = xml_scraper.scrape(selector, "style_content")

        assert "<background>" in value
        assert "<foreground>" in value

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_style_tag_tag_extraction(self, hass: HomeAssistant, xml_scraper):
        """Test extract='tag' on an XML <style> element returns full outer XML."""
        await xml_scraper.set_content(SAMPLE_XML_HTML_TAG_NAMES)

        selector = Selector(hass, {
            "select": Template("style", hass),
            "extract": "tag",
        })
        value = xml_scraper.scrape(selector, "style_tag")

        assert '<style name="dark_mode">' in value
        assert "</style>" in value


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestXmlErrorHandling:
    """Test error handling for XML scraping."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_nonexistent_selector_raises_error(self, hass: HomeAssistant, xml_scraper):
        """Test that a nonexistent CSS selector raises ValueError."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {"select": Template("nonexistent_element", hass)})

        with pytest.raises(ValueError, match="Could not find a tag"):
            xml_scraper.scrape(selector, "missing")

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_malformed_xml_still_parses(self, hass: HomeAssistant, xml_scraper):
        """Test that malformed XML is handled gracefully by lxml-xml parser."""
        # lxml-xml may handle malformed XML differently than lxml (html)
        # It should still create a soup object (lxml is lenient)
        await xml_scraper.set_content(SAMPLE_XML_MALFORMED)

        # Should be parseable (lxml parser is lenient with XML)
        assert xml_scraper._soup is not None

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_empty_select_list_returns_empty_string(
        self, hass: HomeAssistant, xml_scraper
    ):
        """Test that select_list with no matches returns empty string."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        selector = Selector(hass, {"select_list": Template("nonexistent", hass)})
        value = xml_scraper.scrape(selector, "empty_list")

        assert value == ""


# ============================================================================
# Parser Factory Integration Tests
# ============================================================================


class TestXmlParserFactory:
    """Test ParserFactory correctly handles XML parser configuration."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_lxml_xml_parser_name(self, hass: HomeAssistant, xml_scraper):
        """Test that the scraper uses lxml-xml parser."""
        # Verify the parser factory was configured with lxml-xml
        html_parser = xml_scraper._parser_factory._parsers[1]
        assert html_parser._parser_name == "lxml-xml"
        assert html_parser.name == "xml (lxml-xml)"

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_not_detected_as_json(self, hass: HomeAssistant, xml_scraper):
        """Test that XML content is not mistakenly detected as JSON."""
        await xml_scraper.set_content(SAMPLE_XML_WEATHER)

        assert xml_scraper._is_json is False

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.timeout(5)
    async def test_xml_with_leading_whitespace_not_json(self, hass: HomeAssistant, xml_scraper):
        """Test that XML with leading whitespace is not detected as JSON."""
        content = "   \n" + SAMPLE_XML_WEATHER
        await xml_scraper.set_content(content)

        assert xml_scraper._is_json is False
        assert xml_scraper._soup is not None
