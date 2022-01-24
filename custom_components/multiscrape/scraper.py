"""Support for multiscrape requests."""
import logging

from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 10
_LOGGER = logging.getLogger(__name__)


class Scraper:
    """Class for handling the retrieval and scraping of data."""

    def __init__(
        self,
        hass,
        file_manager,
        http,
        form_submitter,
        config_name,
        method,
        resource,
        request_headers,
        params,
        data,
        parser,
    ):
        """Initialize the data object."""
        _LOGGER.debug("%s # Initializing scraper", config_name)

        self._hass = hass
        self._file_manager = file_manager
        self._http = http
        self._config_name = config_name
        self._method = method
        self._resource = resource
        self._request_headers = request_headers
        self._params = params
        self._request_data = data
        self._parser = parser
        self._async_client = None
        self._form_submitter = form_submitter
        self.data = None

    @property
    def name(self):
        return self._config_name

    def set_url(self, url):
        """Set url."""
        self._resource = url

    async def async_update(self):
        """Get the latest data from REST service with provided method."""
        _LOGGER.debug("%s # Refresh triggered", self._config_name)

        if self._file_manager:
            _LOGGER.debug(
                "%s # Deleting logging files from previous run", self._config_name
            )
            try:
                await self._hass.async_add_executor_job(self._file_manager.empty_folder)
            except Exception as ex:
                _LOGGER.error(
                    "%s # Error deleting files from previous run: %s",
                    self._config_name,
                    ex,
                )

        if self._form_submitter and self._form_submitter.should_submit:

            try:
                result = await self._form_submitter.async_submit(self._resource)

                if result:
                    _LOGGER.debug(
                        "%s # Using response from form-submit as data. Now ready to be scraped by sensors.",
                        self._config_name,
                    )
                    await self._set_content(result)
                    return
            except Exception as ex:
                _LOGGER.error(
                    "%s # Exception in form-submit feature. Will continue trying to scrape target page.\n%s",
                    self._config_name,
                    ex,
                )

        else:
            _LOGGER.debug(
                "%s # Skip submitting form because it was already submitted and submit_once is True",
                self._config_name,
            )

        await self._async_update_data()

    async def _set_content(self, content):
        self.data = content

        if content[0] not in ["{", "["]:
            try:
                _LOGGER.debug(
                    "%s # Loading the content in BeautifulSoup.",
                    self._config_name,
                )
                self.soup = BeautifulSoup(self.data, self._parser)
                self.soup.prettify()
                if self._file_manager:
                    filename = "page_soup.txt"
                    try:
                        await self._hass.async_add_executor_job(
                            self._file_manager.write, filename, self.soup
                        )
                    except Exception as ex:
                        _LOGGER.error(
                            "%s # Unable to write BeautifulSoup result to file: %s. \nException: %s",
                            self._config_name,
                            filename,
                            ex,
                        )
                    _LOGGER.debug(
                        "%s # BeautifulSoup content written to file: %s (this is data where the CSS selectors will be applied on)",
                        self._config_name,
                        filename,
                    )

            except Exception as ex:
                _LOGGER.error(
                    "%s # Unable to parse response with BeautifulSoup: %s",
                    self._config_name,
                    ex,
                )

    async def _async_update_data(self):
        _LOGGER.debug("%s # Updating data from %s", self._config_name, self._resource)
        try:
            response = await self._http.async_request(
                "page",
                self._method,
                self._resource,
                self._request_data,
                self._request_headers,
                self._params,
            )
            await self._set_content(response.text)
            _LOGGER.debug(
                "%s # Data succesfully refreshed. Sensors will now start scraping to update.",
                self._config_name,
            )
        except Exception as ex:
            _LOGGER.error(
                "%s # Updating failed with exception: %s",
                self._config_name,
                ex,
            )
            self.data = None
            self.soup = None

    def scrape(self, selector, sensor, attribute=None):
        # This is required as this function is called separately for sensors and attributes
        log_prefix = f"{self._config_name} # {sensor}"
        if attribute:
            log_prefix = log_prefix + f"# {attribute}"

        try:
            if selector.just_value:
                _LOGGER.debug("%s # Applying value_template only.", log_prefix)
                return selector.value_template.async_render_with_possible_json_value(
                    self.data, None
                )

            if selector.is_list:
                tags = self.soup.select(selector.list)
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
                tag = self.soup.select_one(selector.element)
                _LOGGER.debug("%s # Tag selected: %s", log_prefix, tag)
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
                _LOGGER.debug(
                    "%s # Applying value_template on selector result", log_prefix
                )
                value = selector.value_template.async_render(
                    variables={"value": value}, parse_result=False
                )

            _LOGGER.debug("%s # Final selector value: %s", log_prefix, value)
            return value
        except Exception:
            if self._form_submitter:
                self._form_submitter.notify_scrape_exception()
            raise
