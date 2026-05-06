"""Content parsers for multiscrape using the Strategy pattern."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


class ContentParser(ABC):
    """Base class for content parsers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return parser name for logging."""

    @abstractmethod
    def can_parse(self, content: str) -> bool:
        """Check if this parser can handle the content."""

    @abstractmethod
    async def parse(self, content: str, hass: Any) -> Any:
        """Parse content and return parsed structure."""


class HtmlParser(ContentParser):
    """Parse HTML/XML content using BeautifulSoup."""

    def __init__(self, parser_name: str = "lxml"):
        """Initialize markup parser."""
        self._parser_name = parser_name

    @property
    def name(self) -> str:
        """Return parser name."""
        if self._parser_name == "lxml-xml":
            return f"xml ({self._parser_name})"
        return f"html ({self._parser_name})"

    def can_parse(self, content: str) -> bool:
        """HTML parser handles anything that's not JSON."""
        content_stripped = content.lstrip() if content else ""
        if not content_stripped:
            return True
        return content_stripped[0] not in ("{", "[")

    async def parse(self, content: str, hass: Any) -> BeautifulSoup:
        """Parse HTML content with BeautifulSoup."""
        return await hass.async_add_executor_job(
            BeautifulSoup, content, self._parser_name
        )


class JsonDetector(ContentParser):
    """Detects JSON content. Does not parse it (JSON uses value_template only)."""

    @property
    def name(self) -> str:
        """Return parser name."""
        return "json"

    def can_parse(self, content: str) -> bool:
        """Check if content looks like JSON."""
        content_stripped = content.lstrip() if content else ""
        return bool(content_stripped) and content_stripped[0] in ("{", "[")

    async def parse(self, content: str, hass: Any) -> None:
        """JSON is not parsed into a queryable structure."""
        return None


class ParserFactory:
    """Selects the appropriate parser for content."""

    def __init__(self, parser_name: str):
        """Initialize with the HTML parser name."""
        self._parsers: list[ContentParser] = [
            JsonDetector(),
            HtmlParser(parser_name),
        ]

    def get_parser(self, content: str) -> ContentParser:
        """Get appropriate parser for content."""
        for parser in self._parsers:
            if parser.can_parse(content):
                return parser
        # Fallback to HTML (should never happen since HtmlParser accepts empty)
        return self._parsers[-1]
