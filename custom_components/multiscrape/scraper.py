"""Support for multiscrape requests."""
import logging

from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 10
_LOGGER = logging.getLogger(__name__)


class Scraper:
    """Class for handling the retrieval and scraping of data."""

    def __init__(
        self,
        config_name,
        hass,
        file_manager,
        parser,
    ):
        """Initialize the data object."""
        _LOGGER.debug("%s # Initializing scraper", config_name)

        self._hass = hass
        self._file_manager = file_manager
        self._config_name = config_name
        self._parser = parser
        self._soup = None
        self._data = None
        self.reset()

    @property
    def has_data(self):
        return self._data is not None

    @property
    def name(self):
        return self._config_name

    def reset(self):
        self._data = None
        self._soup = None

    async def set_content(self, content):
        self._data = content

        if content[0] not in ["{", "["]:
            try:
                _LOGGER.debug(
                    "%s # Loading the content in BeautifulSoup.",
                    self._config_name,
                )
                self._soup = BeautifulSoup(self._data, self._parser)
                self._soup.prettify()
                if self._file_manager:
                    await self._async_file_log("page_soup", self._soup)

            except Exception as ex:
                self.reset()
                _LOGGER.error(
                    "%s # Unable to parse response with BeautifulSoup: %s",
                    self._config_name,
                    ex,
                )
                raise

    def scrape(self, selector, sensor, attribute=None):
        # This is required as this function is called separately for sensors and attributes
        log_prefix = f"{self._config_name} # {sensor}"
        if attribute:
            log_prefix = log_prefix + f"# {attribute}"

        if selector.just_value:
            _LOGGER.debug("%s # Applying value_template only.", log_prefix)
            return selector.value_template.async_render_with_possible_json_value(
                self._data, None
            )

        if selector.is_list:
            tags = self._soup.select(selector.list)
            _LOGGER.debug("%s # List selector selected tags: %s", log_prefix, tags)
            if selector.attribute is not None:
                _LOGGER.debug(
                    "%s # Try to find attributes: %s",
                    log_prefix,
                    selector.attribute,
                )
                values = [tag[selector.attribute] for tag in tags]
            else:
                values = [tag.text for tag in tags]
            value = ",".join(values)
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
                if tag.name in ("style", "script", "template"):
                    value = tag.string
                else:
                    value = tag.text
            _LOGGER.debug("%s # Selector result: %s", log_prefix, value)

        if value is not None and selector.value_template is not None:
            _LOGGER.debug("%s # Applying value_template on selector result", log_prefix)
            value = selector.value_template.async_render(
                variables={"value": value}, parse_result=False
            )

        _LOGGER.debug("%s # Final selector value: %s", log_prefix, value)
        return value

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
