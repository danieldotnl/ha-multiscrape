"""Value extraction from parsed HTML content."""
from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import Tag

if TYPE_CHECKING:
    from .selector import Selector


class ValueExtractor:
    """Extracts values from BeautifulSoup elements."""

    def __init__(self, separator: str = ","):
        """Initialize value extractor."""
        self._separator = separator

    def extract_single(self, element: Tag, selector: Selector) -> str:
        """Extract a value from a single element."""
        if selector.attribute is not None:
            return element[selector.attribute]
        return self._extract_tag_value(element, selector)

    def extract_list(self, elements: list[Tag], selector: Selector) -> str:
        """Extract values from a list of elements and join with separator."""
        if selector.attribute is not None:
            values = [elem[selector.attribute] for elem in elements]
        else:
            values = [self._extract_tag_value(elem, selector) for elem in elements]
        return self._separator.join(values)

    @staticmethod
    def _extract_tag_value(tag: Tag, selector: Selector) -> str:
        """Extract value from HTML tag based on extract mode."""
        if tag.name in ("style", "script", "template"):
            return tag.string or ""
        if selector.extract == "text":
            return tag.text
        elif selector.extract == "content":
            return ''.join(map(str, tag.contents))
        elif selector.extract == "tag":
            return str(tag)
        return tag.text
