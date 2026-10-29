"""Support for multiscrape requests."""

import json
import logging
from collections.abc import Callable, Iterable
from typing import Any

from bs4 import BeautifulSoup

from .const import CONF_PARSER, CONF_SEPARATOR
from .extractors import ValueExtractor
from .parsers import JsonParser, ParserFactory
from .scrape_context import ScrapeContext
from .selector import Selector

DEFAULT_TIMEOUT = 10
_LOGGER = logging.getLogger(__name__)


def create_scraper(config_name, config, hass, file_manager):
    """Create a scraper instance."""
    _LOGGER.debug("%s # Creating scraper", config_name)
    parser = config.get(CONF_PARSER)
    separator = config.get(CONF_SEPARATOR)

    return Scraper(
        config_name,
        hass,
        file_manager,
        parser,
        separator,
    )


class Scraper:
    """Orchestrates parsing and value extraction."""

    def __init__(
        self,
        config_name,
        hass,
        file_manager,
        parser,
        separator,
    ):
        """Initialize the data object."""
        _LOGGER.debug("%s # Initializing scraper", config_name)

        self._hass = hass
        self._file_manager = file_manager
        self._config_name = config_name
        self._parser_factory = ParserFactory(parser)
        self._extractor = ValueExtractor(separator)
        self._soup: BeautifulSoup = None
        self._data = None
        self._is_json = False
        # Selectors whose CSS selection runs in the executor on every
        # set_content, and the outcome of that run: the extracted value, or
        # the exception the extraction raised.
        self._selectors: dict[Selector, None] = {}
        self._extracted: dict[Selector, Any] = {}
        self.reset()

    @property
    def name(self):
        """Property for config name."""
        return self._config_name

    def reset(self):
        """Reset the scraper object."""
        self._data = None
        self._soup = None
        self._is_json = False
        self._extracted = {}

    def register_selectors(self, selectors: Iterable[Selector]) -> Callable[[], None]:
        """Have the selection for these selectors run off the event loop.

        Returns a callback that unregisters them again.
        """
        selectors = [selector for selector in selectors if not selector.just_value]
        for selector in selectors:
            self._selectors[selector] = None

        def _unregister():
            for selector in selectors:
                self._selectors.pop(selector, None)
                self._extracted.pop(selector, None)

        return _unregister

    @property
    def formatted_content(self):
        """Return the content for display: HTML prettified, JSON pretty-printed, or raw."""
        if self._soup:
            return self._soup.prettify()
        if self._is_json and self._data:
            try:
                return json.dumps(
                    json.loads(self._data), indent=2, ensure_ascii=False
                )
            except (json.JSONDecodeError, RecursionError):
                # Detected as JSON-shaped but unparsable — fall back to raw.
                return self._data
        return self._data

    async def async_formatted_content(self):
        """Return formatted_content, formatted in the executor as pages can be large."""
        return await self._hass.async_add_executor_job(lambda: self.formatted_content)

    async def set_content(self, content):
        """Set the content to be scraped."""
        self._data = content
        self._extracted = {}
        parser = self._parser_factory.get_parser(content)

        if isinstance(parser, JsonParser):
            _LOGGER.debug(
                "%s # Response detected as JSON; skipping BeautifulSoup parsing.",
                self._config_name,
            )
            self._is_json = True
            if self._file_manager:
                await self._async_file_log(
                    "page_json", await self.async_formatted_content()
                )
            return

        try:
            _LOGGER.debug(
                "%s # Loading the content in BeautifulSoup.",
                self._config_name,
            )
            self._soup = await parser.parse(content, self._hass)

            if self._file_manager:
                await self._async_file_log(
                    "page_soup", await self.async_formatted_content()
                )

        except Exception as ex:
            self.reset()
            _LOGGER.error(
                "%s # Unable to parse response with BeautifulSoup: %s",
                self._config_name,
                ex,
            )
            raise

        await self._async_extract_registered()

    async def _async_extract_registered(self):
        """Run the selection for all registered selectors in the executor.

        Selecting can take seconds on large pages (#633), so it must not block
        the event loop. The select templates are rendered here first, since
        rendering belongs on the loop.
        """
        soup = self._soup
        extracted = {}
        jobs = []
        for selector in self._selectors:
            try:
                css = selector.list if selector.is_list else selector.element
            except Exception as ex:
                extracted[selector] = ex
            else:
                jobs.append((selector, css))

        if jobs:
            extracted.update(
                await self._hass.async_add_executor_job(self._extract_batch, soup, jobs)
            )
        # Don't store results for content that was replaced or reset meanwhile,
        # nor for selectors that were unregistered meanwhile.
        if self._soup is soup:
            self._extracted = {
                selector: value
                for selector, value in extracted.items()
                if selector in self._selectors
            }

    def _extract_batch(self, soup, jobs):
        """Extract the values for a batch of (selector, css) jobs. Runs in the executor."""
        results = {}
        for selector, css in jobs:
            try:
                results[selector] = self._extract_value(
                    soup, selector, css, self._make_log_prefix(selector.name, None)
                )
            except Exception as ex:
                # Without its traceback, the stored exception doesn't keep
                # this run's frames (and with them the soup) alive.
                results[selector] = ex.with_traceback(None)
        return results

    def scrape(
        self, selector, sensor, attribute=None, context: ScrapeContext | None = None
    ):
        """Scrape based on given selector the data."""
        if context is None:
            context = ScrapeContext.empty()

        log_prefix = self._make_log_prefix(sensor, attribute)

        if selector.just_value:
            _LOGGER.debug("%s # Applying value_template only.", log_prefix)
            return selector.value_template.async_render_with_possible_json_value(
                self._data,
                None,
                variables=context.to_template_variables(),
                parse_result=True,
            )

        if self._is_json:
            raise ValueError(
                "JSON cannot be scraped. Please provide a value template to parse JSON response."
            )

        if selector in self._extracted:
            value = self._extracted[selector]
            if isinstance(value, Exception):
                raise value
            _LOGGER.debug("%s # Selected off the event loop: %s", log_prefix, value)
        else:
            _LOGGER.debug(
                "%s # Selector not precomputed, selecting on the event loop", log_prefix
            )
            css = selector.list if selector.is_list else selector.element
            value = self._extract_value(self._soup, selector, css, log_prefix)

        if value is not None and selector.value_template is not None:
            _LOGGER.debug("%s # Applying value_template on selector result", log_prefix)
            render_ctx = context.with_current_value(value)
            value = selector.value_template.async_render(
                variables=render_ctx.to_template_variables(), parse_result=True
            )

        _LOGGER.debug(
            "%s # Final selector value: %s of type %s", log_prefix, value, type(value)
        )
        return value

    def _extract_value(self, soup, selector, css, log_prefix):
        """Select the tag(s) for css and delegate extraction to ValueExtractor."""
        if selector.is_list:
            tags = soup.select(css)
            _LOGGER.debug("%s # List selector selected tags: %s", log_prefix, tags)
            return self._extractor.extract_list(tags, selector)
        else:
            tag = soup.select_one(css)
            _LOGGER.debug("%s # Tag selected: %s", log_prefix, tag)
            if tag is None:
                raise ValueError("Could not find a tag for given selector")
            return self._extractor.extract_single(tag, selector)

    def _make_log_prefix(self, sensor, attribute):
        """Create log prefix for messages."""
        prefix = f"{self._config_name} # {sensor}"
        if attribute:
            prefix = prefix + f"# {attribute}"
        return prefix

    async def _async_file_log(self, content_name, content):
        try:
            filename = f"{content_name}.txt"
            await self._hass.async_add_executor_job(
                self._file_manager.write, filename, content
            )
        except Exception as ex:
            _LOGGER.error(
                "%s # Unable to write %s to file: %s. \nException: %s",
                self._config_name,
                content_name,
                filename,
                ex,
            )
        _LOGGER.debug(
            "%s # %s written to file: %s",
            self._config_name,
            content_name,
            filename,
        )
