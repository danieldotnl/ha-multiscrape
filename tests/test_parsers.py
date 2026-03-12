"""Unit tests for the parsers module."""

import pytest
from bs4 import BeautifulSoup
from homeassistant.core import HomeAssistant

from custom_components.multiscrape.parsers import (HtmlParser, JsonDetector,
                                                   ParserFactory)

# ============================================================================
# JsonDetector tests
# ============================================================================


class TestJsonDetector:
    """Tests for JsonDetector."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = JsonDetector()

    def test_name(self):
        """Test that JsonDetector reports its name as 'json'."""
        assert self.detector.name == "json"

    def test_can_parse_json_object(self):
        """Test that JSON objects are detected."""
        assert self.detector.can_parse('{"key": "value"}') is True

    def test_can_parse_json_array(self):
        """Test that JSON arrays are detected."""
        assert self.detector.can_parse('[1, 2, 3]') is True

    def test_can_parse_json_with_leading_whitespace(self):
        """Test that JSON with leading whitespace is detected."""
        assert self.detector.can_parse('  {"key": "value"}') is True

    def test_cannot_parse_html(self):
        """Test that HTML content is not detected as JSON."""
        assert self.detector.can_parse("<html><body>Hello</body></html>") is False

    def test_cannot_parse_empty_string(self):
        """Test that empty string is not detected as JSON."""
        assert self.detector.can_parse("") is False

    def test_cannot_parse_plain_text(self):
        """Test that plain text is not detected as JSON."""
        assert self.detector.can_parse("Hello world") is False

    @pytest.mark.async_test
    async def test_parse_returns_none(self, hass: HomeAssistant):
        """Test that parse returns None since JSON is not parsed."""
        result = await self.detector.parse('{"key": "value"}', hass)
        assert result is None


# ============================================================================
# HtmlParser tests
# ============================================================================


class TestHtmlParser:
    """Tests for HtmlParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = HtmlParser("lxml")

    def test_name(self):
        """Test that HtmlParser reports its parser name."""
        assert self.parser.name == "html (lxml)"

    def test_can_parse_html(self):
        """Test that HTML content is accepted."""
        assert self.parser.can_parse("<html><body>Hello</body></html>") is True

    def test_can_parse_empty_string(self):
        """Test that empty string is accepted as HTML."""
        assert self.parser.can_parse("") is True

    def test_can_parse_plain_text(self):
        """Test that plain text is accepted as HTML."""
        assert self.parser.can_parse("Hello world") is True

    def test_cannot_parse_json_object(self):
        """Test that JSON objects are not accepted as HTML."""
        assert self.parser.can_parse('{"key": "value"}') is False

    def test_cannot_parse_json_array(self):
        """Test that JSON arrays are not accepted as HTML."""
        assert self.parser.can_parse('[1, 2, 3]') is False

    @pytest.mark.async_test
    async def test_parse_returns_beautifulsoup(self, hass: HomeAssistant):
        """Test that parse returns a BeautifulSoup instance."""
        result = await self.parser.parse("<div>Hello</div>", hass)
        assert isinstance(result, BeautifulSoup)

    @pytest.mark.async_test
    async def test_parse_content_is_queryable(self, hass: HomeAssistant):
        """Test that parsed content can be queried with CSS selectors."""
        result = await self.parser.parse('<div class="test">Hello</div>', hass)
        tag = result.select_one(".test")
        assert tag is not None
        assert tag.text == "Hello"


# ============================================================================
# ParserFactory tests
# ============================================================================


class TestParserFactory:
    """Tests for ParserFactory."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = ParserFactory("lxml")

    def test_selects_json_detector_for_json_object(self):
        """Test that factory selects JsonDetector for JSON objects."""
        parser = self.factory.get_parser('{"key": "value"}')
        assert isinstance(parser, JsonDetector)

    def test_selects_json_detector_for_json_array(self):
        """Test that factory selects JsonDetector for JSON arrays."""
        parser = self.factory.get_parser('[1, 2, 3]')
        assert isinstance(parser, JsonDetector)

    def test_selects_html_parser_for_html(self):
        """Test that factory selects HtmlParser for HTML content."""
        parser = self.factory.get_parser("<html>Hello</html>")
        assert isinstance(parser, HtmlParser)

    def test_selects_html_parser_for_empty_string(self):
        """Test that factory selects HtmlParser for empty string."""
        parser = self.factory.get_parser("")
        assert isinstance(parser, HtmlParser)

    def test_selects_html_parser_for_plain_text(self):
        """Test that factory selects HtmlParser for plain text."""
        parser = self.factory.get_parser("Hello world")
        assert isinstance(parser, HtmlParser)
