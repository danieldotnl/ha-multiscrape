"""Support for multiscrape requests."""
import logging

from bs4 import BeautifulSoup

from .const import CONF_PARSER, CONF_SEPARATOR

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
    """Class for handling the retrieval and scraping of data."""

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
        self._parser = parser
        self._soup: BeautifulSoup = None
        self._data = None
        self._separator = separator
        self.reset()

    @property
    def name(self):
        """Property for config name."""
        return self._config_name

    def reset(self):
        """Reset the scraper object."""
        self._data = None
        self._soup = None

    @property
    def formatted_content(self):
        """Property for getting the content. HTML will be prettified."""
        if self._soup:
            return self._soup.prettify()
        return self._data

    async def set_content(self, content):
        """Set the content to be scraped."""
        self._data = content

        if content[0] in ["{", "["]:
            _LOGGER.debug(
                "%s # Response seems to be json. Skip parsing with BeautifulSoup.",
                self._config_name,
            )
        else:
            try:
                _LOGGER.debug(
                    "%s # Loading the content in BeautifulSoup.",
                    self._config_name,
                )
                self._soup = await self._hass.async_add_executor_job(
                    BeautifulSoup, self._data, self._parser
                )

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

    def scrape(self, selector, sensor, attribute=None, variables: dict = {}):
        """Scrape based on given selector the data."""
        # This is required as this function is called separately for sensors and attributes
        log_prefix = f"{self._config_name} # {sensor}"
        if attribute:
            log_prefix = log_prefix + f"# {attribute}"

        if selector.just_value:
            _LOGGER.debug("%s # Applying value_template only.", log_prefix)
            result = selector.value_template.async_render_with_possible_json_value(
                self._data, None, variables=variables
            )
            return selector.value_template._parse_result(result)

        if self._data[0] in ["{", "["]:
            raise ValueError(
                "JSON cannot be scraped. Please provide a value template to parse JSON response."
            )

        if selector.is_list:
            tags = self._soup.select(selector.list)
            _LOGGER.debug("%s # List selector selected tags: %s",
                          log_prefix, tags)
            if selector.attribute is not None:
                _LOGGER.debug(
                    "%s # Try to find attributes: %s",
                    log_prefix,
                    selector.attribute,
                )
                values = [tag[selector.attribute] for tag in tags]
            else:
                values = [self.extract_tag_value(tag, selector) for tag in tags]
            value = self._separator.join(values)
            _LOGGER.debug("%s # List selector csv: %s", log_prefix, value)

        else:
            tag = self._soup.select_one(selector.element)
            _LOGGER.debug("%s # Tag selected: %s", log_prefix, tag)
            if tag is None:
                raise ValueError("Could not find a tag for given selector")

            if selector.attribute is not None:
                _LOGGER.debug(
                    "%s # Try to find attribute: %s", log_prefix, selector.attribute
                )
                value = tag[selector.attribute]
            else:
                value = self.extract_tag_value(tag, selector)
            _LOGGER.debug("%s # Selector result: %s", log_prefix, value)

        if value is not None and selector.value_template is not None:
            _LOGGER.debug(
                "%s # Applying value_template on selector result", log_prefix)
            variables["value"] = value
            value = selector.value_template.async_render(variables=variables, parse_result=True
            )

        _LOGGER.debug(
            "%s # Final selector value: %s of type %s", log_prefix, value, type(
                value)
        )
        return value

    def extract_tag_value(self, tag, selector):
        """Extract value from a tag."""
        if tag.name in ("style", "script", "template"):
            return tag.string
        else:
            if selector.extract == "text":
                return tag.text
            elif selector.extract == "content":
                return ''.join(map(str, tag.contents))
            elif selector.extract == "tag":
                return str(tag)

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
