"""Integration tests for scraper class.

These tests verify the Scraper class works correctly with Selector and BeautifulSoup
to extract data from HTML content using CSS selectors.
"""

import re

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import DEFAULT_SEPARATOR
from custom_components.multiscrape.scraper import Scraper
from custom_components.multiscrape.selector import Selector

from .fixtures.html_samples import (SAMPLE_HTML_EMPTY, SAMPLE_HTML_FULL,
                                    SAMPLE_HTML_LIST, SAMPLE_HTML_MALFORMED,
                                    SAMPLE_HTML_SPECIAL_TAGS)
from .fixtures.json_samples import SAMPLE_JSON_SIMPLE


@pytest.fixture
def scraper_instance(hass: HomeAssistant):
    """Create a Scraper instance for testing."""
    return Scraper("test_scraper", hass, None, "lxml", DEFAULT_SEPARATOR)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
@pytest.mark.parametrize(
    "selector_config,expected_value",
    [
        # Test text extraction
        (
            {"select": ".current-version h1", "extract": "text"},
            "Current Version: 2024.8.3",
        ),
        # Test content extraction (inner HTML) - note: may include trailing newline
        (
            {"select": ".links", "extract": "content"},
            '<a href="/latest-release-notes/">Release notes</a>',
        ),
        # Test tag extraction (outer HTML) - note: may include trailing newline
        (
            {"select": ".links", "extract": "tag"},
            '<div class="links" style="links"><a href="/latest-release-notes/">Release notes</a></div>',
        ),
        # Test attribute extraction
        (
            {"select": ".links a", "attribute": "href"},
            "/latest-release-notes/",
        ),
    ],
)
async def test_scraper_extraction_methods(
    hass: HomeAssistant, scraper_instance, selector_config, expected_value
):
    """Test different extraction methods (text, content, tag, attribute)."""
    # Arrange
    await scraper_instance.set_content(SAMPLE_HTML_FULL)

    # Convert string select to Template if present
    if "select" in selector_config:
        selector_config["select"] = Template(selector_config["select"], hass)

    selector = Selector(hass, selector_config)

    # Act
    value = scraper_instance.scrape(selector, "test_sensor")

    # Assert
    # Normalize whitespace for comparison (BeautifulSoup may add newlines/spaces)
    normalized_value = re.sub(r"\s+", " ", value).strip()
    normalized_expected = re.sub(r"\s+", " ", expected_value).strip()
    assert normalized_value == normalized_expected


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_with_list_selector(hass: HomeAssistant, scraper_instance):
    """Test scraping multiple elements using list selector."""
    # Arrange
    await scraper_instance.set_content(SAMPLE_HTML_LIST)

    selector_config = {
        "select_list": Template(".item", hass),
        "extract": "text",
    }
    selector = Selector(hass, selector_config)

    # Act
    value = scraper_instance.scrape(selector, "test_sensor")

    # Assert
    # Should return comma-separated values (DEFAULT_SEPARATOR is ", ")
    # Note: DEFAULT_SEPARATOR is actually "," not ", " - let's check actual output
    assert value == "Item 1,Item 2,Item 3"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_with_special_tags(hass: HomeAssistant, scraper_instance):
    """Test extraction from special tags (script, style, template)."""
    # Arrange
    await scraper_instance.set_content(SAMPLE_HTML_SPECIAL_TAGS)

    # Test script tag
    selector_config = {"select": Template("script", hass)}
    selector = Selector(hass, selector_config)
    value = scraper_instance.scrape(selector, "test_sensor")
    assert 'console.log("test");' in value

    # Test style tag
    selector_config = {"select": Template("style", hass)}
    selector = Selector(hass, selector_config)
    value = scraper_instance.scrape(selector, "test_sensor")
    assert ".test { color: red; }" in value


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_selector_not_found_raises_error(
    hass: HomeAssistant, scraper_instance
):
    """Test that scraper raises ValueError when selector matches nothing."""
    # Arrange
    await scraper_instance.set_content(SAMPLE_HTML_FULL)

    selector_config = {
        "select": Template(".nonexistent-class", hass),
        "extract": "text",
    }
    selector = Selector(hass, selector_config)

    # Act & Assert
    with pytest.raises(ValueError, match="Could not find a tag for given selector"):
        scraper_instance.scrape(selector, "test_sensor")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_handles_json_content(hass: HomeAssistant, scraper_instance):
    """Test that scraper detects and handles JSON content correctly."""
    # Arrange
    await scraper_instance.set_content(SAMPLE_JSON_SIMPLE)

    # JSON content should not be parsed by BeautifulSoup
    assert scraper_instance._soup is None
    assert scraper_instance._data == SAMPLE_JSON_SIMPLE


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_json_without_value_template_raises_error(
    hass: HomeAssistant, scraper_instance
):
    """Test that attempting to scrape JSON without value_template raises error."""
    # Arrange
    await scraper_instance.set_content(SAMPLE_JSON_SIMPLE)

    selector_config = {
        "select": Template(".something", hass),
        "extract": "text",
    }
    selector = Selector(hass, selector_config)

    # Act & Assert
    with pytest.raises(
        ValueError,
        match="JSON cannot be scraped. Please provide a value template to parse JSON response.",
    ):
        scraper_instance.scrape(selector, "test_sensor")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_reset_clears_content(hass: HomeAssistant, scraper_instance):
    """Test that reset() clears both data and soup."""
    # Arrange
    await scraper_instance.set_content(SAMPLE_HTML_FULL)
    assert scraper_instance._data is not None
    assert scraper_instance._soup is not None

    # Act
    scraper_instance.reset()

    # Assert
    assert scraper_instance._data is None
    assert scraper_instance._soup is None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_handles_empty_content(hass: HomeAssistant, scraper_instance):
    """Test scraper behavior with empty content.

    Current behavior: Empty content is parsed by BeautifulSoup, creating an empty soup.
    This allows the scraper to continue operating even with empty responses.
    """
    # Arrange & Act
    await scraper_instance.set_content(SAMPLE_HTML_EMPTY)

    # Assert
    assert scraper_instance._data == SAMPLE_HTML_EMPTY
    # BeautifulSoup creates an empty soup object for empty string
    assert scraper_instance._soup is not None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_handles_malformed_html(hass: HomeAssistant, scraper_instance):
    """Test that scraper handles malformed HTML gracefully."""
    # Arrange & Act
    await scraper_instance.set_content(SAMPLE_HTML_MALFORMED)

    # Assert - BeautifulSoup should parse it without raising
    assert scraper_instance._soup is not None
    # Can still extract from the parsed structure
    selector_config = {
        "select": Template(".unclosed", hass),
        "extract": "text",
    }
    selector = Selector(hass, selector_config)
    value = scraper_instance.scrape(selector, "test_sensor")
    assert "This paragraph is not closed" in value


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scraper_formatted_content_prettifies_html(
    hass: HomeAssistant, scraper_instance
):
    """Test that formatted_content returns prettified HTML."""
    # Arrange
    await scraper_instance.set_content("<div><p>Test</p></div>")

    # Act
    formatted = scraper_instance.formatted_content

    # Assert
    # Prettified HTML should have newlines and indentation
    # BeautifulSoup wraps content in html/body tags and formats with newlines
    assert "\n" in formatted
    assert "<div>" in formatted
    assert "Test" in formatted
    # Verify it's actually formatted (has indentation)
    assert "  " in formatted  # Multiple spaces indicate indentation
