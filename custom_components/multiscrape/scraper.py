"""Support for multiscrape requests."""
import logging

from bs4 import BeautifulSoup

from .const import CONF_PARSER, CONF_SEPARATOR
from .extractors import ValueExtractor
from .parsers import JsonDetector, ParserFactory
from .scrape_context import ScrapeContext

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

    @property
    def formatted_content(self):
        """Property for getting the content. HTML will be prettified."""
        if self._soup:
            return self._soup.prettify()
        return self._data

    async def set_content(self, content):
        """Set the content to be scraped."""
        self._data = content
        parser = self._parser_factory.get_parser(content)

        if isinstance(parser, JsonDetector):
            _LOGGER.debug(
                "%s # Response seems to be json. Skip parsing with BeautifulSoup.",
                self._config_name,
            )
            self._is_json = True
            return

        try:
            _LOGGER.debug(
                "%s # Loading the content in BeautifulSoup.",
                self._config_name,
            )
            self._soup = await parser.parse(content, self._hass)

            if self._file_manager:
                await self._async_file_log("page_soup", self._soup.prettify())

        except Exception as ex:
            self.reset()
            _LOGGER.error(
                "%s # Unable to parse response with BeautifulSoup: %s",
                self._config_name,
                ex,
            )
            raise

    def scrape(self, selector, sensor, attribute=None, context: ScrapeContext | None = None):
        """Scrape based on given selector the data."""
        if context is None:
            context = ScrapeContext.empty()

        log_prefix = self._make_log_prefix(sensor, attribute)

        if selector.just_value:
            _LOGGER.debug("%s # Applying value_template only.", log_prefix)
            result = selector.value_template.async_render_with_possible_json_value(
                self._data, None, variables=context.to_template_variables()
            )
            return selector.value_template._parse_result(result)

        if self._is_json:
            raise ValueError(
                "JSON cannot be scraped. Please provide a value template to parse JSON response."
            )

        value = self._extract_value(selector, log_prefix)

        if value is not None and selector.value_template is not None:
            _LOGGER.debug(
                "%s # Applying value_template on selector result", log_prefix)
            render_ctx = context.with_current_value(value)
            value = selector.value_template.async_render(
                variables=render_ctx.to_template_variables(), parse_result=True
            )

        _LOGGER.debug(
            "%s # Final selector value: %s of type %s", log_prefix, value, type(
                value)
        )
        return value

    def _extract_value(self, selector, log_prefix):
        """Delegate extraction to ValueExtractor."""
        if selector.is_list:
            tags = self._soup.select(selector.list)
            _LOGGER.debug("%s # List selector selected tags: %s",
                          log_prefix, tags)
            return self._extractor.extract_list(tags, selector)
        else:
            tag = self._soup.select_one(selector.element)
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
