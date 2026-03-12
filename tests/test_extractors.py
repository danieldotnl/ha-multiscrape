"""Unit tests for the extractors module."""

from unittest.mock import MagicMock

from bs4 import BeautifulSoup

from custom_components.multiscrape.extractors import ValueExtractor


def _make_soup(html: str) -> BeautifulSoup:
    """Create a BeautifulSoup from an HTML string."""
    return BeautifulSoup(html, "html.parser")


def _make_selector(extract="text", attribute=None):
    """Create a mock Selector with given extract mode and attribute."""
    selector = MagicMock()
    selector.extract = extract
    selector.attribute = attribute
    return selector


# ============================================================================
# Single element extraction tests
# ============================================================================


class TestExtractSingle:
    """Tests for ValueExtractor.extract_single."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = ValueExtractor(",")

    def test_extract_text(self):
        """Test text extraction from an element."""
        soup = _make_soup('<p class="test">Hello World</p>')
        tag = soup.select_one(".test")
        selector = _make_selector(extract="text")
        assert self.extractor.extract_single(tag, selector) == "Hello World"

    def test_extract_content(self):
        """Test inner HTML extraction from an element."""
        soup = _make_soup('<div class="test"><span>Inner</span> text</div>')
        tag = soup.select_one(".test")
        selector = _make_selector(extract="content")
        result = self.extractor.extract_single(tag, selector)
        assert "<span>Inner</span>" in result
        assert "text" in result

    def test_extract_tag(self):
        """Test outer HTML extraction from an element."""
        soup = _make_soup('<p class="test">Hello</p>')
        tag = soup.select_one(".test")
        selector = _make_selector(extract="tag")
        result = self.extractor.extract_single(tag, selector)
        assert result == '<p class="test">Hello</p>'

    def test_extract_attribute(self):
        """Test attribute extraction from an element."""
        soup = _make_soup('<a href="/link" class="test">Click</a>')
        tag = soup.select_one(".test")
        selector = _make_selector(attribute="href")
        assert self.extractor.extract_single(tag, selector) == "/link"

    def test_extract_script_tag_returns_string(self):
        """Test that script tags return tag.string content."""
        soup = _make_soup('<script>console.log("hi");</script>')
        tag = soup.select_one("script")
        selector = _make_selector(extract="text")
        assert self.extractor.extract_single(tag, selector) == 'console.log("hi");'

    def test_extract_style_tag_returns_string(self):
        """Test that style tags return tag.string content."""
        soup = _make_soup("<style>.foo { color: red; }</style>")
        tag = soup.select_one("style")
        selector = _make_selector(extract="text")
        assert self.extractor.extract_single(tag, selector) == ".foo { color: red; }"

    def test_extract_template_tag_returns_string(self):
        """Test that template tags return tag.string content."""
        soup = _make_soup("<template>Template content</template>")
        tag = soup.select_one("template")
        selector = _make_selector(extract="text")
        assert self.extractor.extract_single(tag, selector) == "Template content"


# ============================================================================
# List extraction tests
# ============================================================================


class TestExtractList:
    """Tests for ValueExtractor.extract_list."""

    def test_extract_list_text(self):
        """Test text extraction from multiple elements."""
        extractor = ValueExtractor(",")
        soup = _make_soup(
            '<ul><li class="item">A</li><li class="item">B</li><li class="item">C</li></ul>'
        )
        tags = soup.select(".item")
        selector = _make_selector(extract="text")
        assert extractor.extract_list(tags, selector) == "A,B,C"

    def test_extract_list_with_custom_separator(self):
        """Test list extraction with a custom separator."""
        extractor = ValueExtractor(" | ")
        soup = _make_soup(
            '<ul><li class="item">A</li><li class="item">B</li></ul>'
        )
        tags = soup.select(".item")
        selector = _make_selector(extract="text")
        assert extractor.extract_list(tags, selector) == "A | B"

    def test_extract_list_attributes(self):
        """Test attribute extraction from multiple elements."""
        extractor = ValueExtractor(",")
        soup = _make_soup(
            '<div><a href="/a" class="link">A</a><a href="/b" class="link">B</a></div>'
        )
        tags = soup.select(".link")
        selector = _make_selector(attribute="href")
        assert extractor.extract_list(tags, selector) == "/a,/b"

    def test_extract_empty_list(self):
        """Test extraction from an empty list returns empty string."""
        extractor = ValueExtractor(",")
        selector = _make_selector(extract="text")
        assert extractor.extract_list([], selector) == ""
