"""Support for multiscrape requests."""
import logging
import os
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util import slugify

from .const import CONF_FORM_INPUT
from .const import CONF_FORM_RESOURCE
from .const import CONF_FORM_RESUBMIT_ERROR
from .const import CONF_FORM_SELECT
from .const import CONF_FORM_SUBMIT_ONCE

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class Scraper:
    """Class for handling the retrieval and scraping of data."""

    def __init__(
        self,
        hass,
        name,
        method,
        resource,
        auth,
        request_headers,
        params,
        data,
        verify_ssl,
        parser,
        form_submit_config,
        timeout=DEFAULT_TIMEOUT,
        log_response=False,
    ):
        """Initialize the data object."""
        _LOGGER.debug("%s # Initializing scraper", name)

        self._hass = hass
        self._name = name
        self._method = method
        self._resource = resource
        self._auth = auth
        self._request_headers = request_headers
        self._params = params
        self._request_data = data
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._parser = parser
        self._async_client = None
        self._form_submit_config = form_submit_config
        self.data = None
        self.last_exception = None
        self._skip_form = False
        self._log_response = log_response

        if form_submit_config:
            _LOGGER.debug("%s # Found form-submit config", self._name)
            self._form_resource = self._form_submit_config.get(CONF_FORM_RESOURCE)
            self._form_select = self._form_submit_config.get(CONF_FORM_SELECT)
            self._form_input = self._form_submit_config.get(CONF_FORM_INPUT)
            self._form_submit_once = self._form_submit_config.get(CONF_FORM_SUBMIT_ONCE)
            self._form_resubmit_error = self._form_submit_config.get(
                CONF_FORM_RESUBMIT_ERROR
            )

        if not self._async_client:
            self._async_client = get_async_client(
                self._hass, verify_ssl=self._verify_ssl
            )

    @property
    def name(self):
        return self._name

    def notify_scrape_exception(self):
        if self._form_submit_config and self._form_resubmit_error:
            _LOGGER.debug(
                "%s # Exception occurred while scraping, will try to resubmit the form next interval.",
                self._name,
            )
            self._skip_form = False

    def set_url(self, url):
        """Set url."""
        self._resource = url

    async def async_update(self):
        """Get the latest data from REST service with provided method."""
        _LOGGER.debug("%s # Refresh triggered", self._name)

        # Do we need to submit a form?
        if self._form_submit_config is None or self._skip_form:
            # No we don't
            if self._skip_form:
                _LOGGER.debug(
                    "%s # Skip submitting form for resource: %s because it was already submitted and submit_once is True",
                    self._name,
                    self._resource,
                )

            await self._async_update_data()

        # Yes we do
        else:
            _LOGGER.debug("%s # Continue with form-submit", self._name)
            try:
                resource = (
                    self._form_resource if self._form_resource else self._resource
                )
                _LOGGER.debug(
                    "%s # Requesting page with form from: %s", self._name, resource
                )
                response = await self._async_request(
                    "form_page",
                    "GET",
                    resource,
                    self._request_headers,
                    self._params,
                    self._auth,
                    self._request_data,
                    self._timeout,
                )
                page = response.text

                form = await self._get_form_data(page)
                form_action = form[0]
                form_method = form[1] if form[1] else "POST"
                form_data = form[2]

                submit_resource = self._determine_submit_resource(form_action)
                _LOGGER.debug(
                    "%s # Determined the url to submit the form to: %s",
                    self._name,
                    submit_resource,
                )
                form_data.update(self._form_input)
                _LOGGER.debug(
                    "%s # Merged input fields with input data in config. Result: %s",
                    self._name,
                    form_data,
                )

                _LOGGER.debug("%s # Going now to submit the form", self._name)
                response = await self._async_request(
                    "form_submit",
                    form_method,
                    submit_resource,
                    self._request_headers,
                    self._params,
                    self._auth,
                    form_data,
                    self._timeout,
                )
                _LOGGER.debug(
                    "%s # Form seems to be submitted succesfully! Now continuing to update data for sensors",
                    self._name,
                )
                if self._form_submit_once:
                    self._skip_form = True

                if not self._form_resource:
                    _LOGGER.debug(
                        "%s # Using response from form-submit as data. Now ready to be scraped by sensors.",
                        self._name,
                    )
                    self.data = response.data
                    return
            except Exception:
                _LOGGER.error(
                    "%s # Exception in form-submit feature. Will continue trying to scrape target page",
                    self._name,
                )

            # If anything goes wrong, still try to continue without submitting the form
            await self._async_update_data()

        if not self.data.startswith("{"):
            try:
                _LOGGER.debug(
                    "%s # Start loading the response in BeautifulSoup.", self._name
                )
                self.soup = BeautifulSoup(self.data, self._parser)
                self.soup.prettify()
                if self._log_response:
                    filename = self._create_filename("page_soup")
                    await self._hass.async_add_executor_job(
                        self._write_file, filename, self.soup
                    )
                    _LOGGER.debug(
                        "%s # Response headers written to file: %s",
                        self._name,
                        filename,
                    )

            except Exception as ex:
                _LOGGER.error("%s # Unable to parse response: %s", self._name, ex)

    async def _async_update_data(self):
        _LOGGER.debug("%s # Updating data from %s", self._name, self._resource)
        try:
            response = await self._async_request(
                "page",
                self._method,
                self._resource,
                self._request_headers,
                self._params,
                self._auth,
                self._request_data,
                self._timeout,
            )
            self.data = response.text
            _LOGGER.debug(
                "%s # Data succesfully refreshed. Sensors will now start scraping to update.",
                self._name,
            )
        except Exception as ex:
            _LOGGER.error(
                "%s # Error! Updating failed with %s",
                self._name,
                ex,
            )
            self.data = None

    def _determine_submit_resource(self, action):
        if action and self._form_resource:
            return urljoin(self._form_resource, action)
        if action:
            return urljoin(self._resource, action)
        if self._form_resource:
            return self._form_resource
        return self._resource

    async def _get_form_data(self, html):
        _LOGGER.debug("%s # Start trying to capture the form in the page", self._name)
        try:
            _LOGGER.debug(
                "%s # Parse HTML with BeautifulSoup parser %s", self._name, self._parser
            )
            soup = BeautifulSoup(html, self._parser)
            soup.prettify()
            if self._log_response:
                filename = self._create_filename("form_page_soup")
                await self._hass.async_add_executor_job(
                    self._write_file, filename, soup
                )
                _LOGGER.debug(
                    "%s # The page with the form parsed by BeautifulSoup has been written to file: %s",
                    self._name,
                    filename,
                )

            _LOGGER.debug(
                "%s # Try to find form with selector %s", self._name, self._form_select
            )
            form = soup.select(self._form_select)[0]
            _LOGGER.debug(
                "%s # Found the form, now finding all input fields", self._name
            )
            elements = form.findAll("input")
            formdata = dict(
                (element.get("name"), element.get("value")) for element in elements
            )
            _LOGGER.debug("%s # Found the following fields: %s", self._name, formdata)

            action = form.get("action")
            method = form.get("method")
            _LOGGER.debug(
                "%s # Found form action %s and method %s", self._name, action, method
            )

            return (action, method, formdata)

        except IndexError as exception:
            _LOGGER.info("%s # Unable to extract form data from.", self._name)
            _LOGGER.debug(
                "%s # Exception extracing form data: %s", self._name, exception
            )
            raise

    def _write_file(self, filename, content):
        try:
            if not os.path.exists(os.path.dirname(filename)):
                try:
                    os.makedirs(os.path.dirname(filename))
                except OSError as exc:  # Guard against race condition
                    if exc.errno != errno.EEXIST:  # noqa: F821
                        raise

            with open(filename, "w", encoding="utf8") as file:
                file.write(str(content))
        except Exception as ex:
            _LOGGER.error(
                "%s # Unable to write response to file: %s. \nException: %s",
                self._name,
                filename,
                ex,
            )

    def _create_filename(self, context):
        folder = slugify(self._name)
        return os.path.join(
            self._hass.config.config_dir, f"multiscrape/{folder}/{context}.txt"
        )

    async def _async_request(
        self, context, method, resource, headers, params, auth, request_data, timeout
    ):
        _LOGGER.debug(
            "%s # Executing %s-request with a %s to url: %s.",
            self._name,
            context,
            method,
            resource,
        )
        try:
            response = await self._async_client.request(
                method,
                resource,
                headers=headers,
                params=params,
                auth=auth,
                data=request_data,
                timeout=self._timeout,
            )

            _LOGGER.debug(
                "%s # Response status code received: %s",
                self._name,
                response.status_code,
            )
            if self._log_response:

                filename = self._create_filename(f"{context}_response_headers")
                await self._hass.async_add_executor_job(
                    self._write_file, filename, response.headers
                )
                _LOGGER.debug(
                    "%s # Response headers written to file: %s",
                    self._name,
                    filename,
                )

                filename = self._create_filename(f"{context}_response_body")
                await self._hass.async_add_executor_job(
                    self._write_file, filename, response.text
                )
                _LOGGER.debug(
                    "%s # Response headers written to file: %s",
                    self._name,
                    filename,
                )

            return response

        except httpx.RequestError as ex:
            _LOGGER.error(
                "%s # Error executing %s request to url: %s.\n Error message:\n %s",
                self._name,
                method,
                resource,
                ex,
            )
            raise

    def scrape(self, selector, sensor, attribute=None):
        # This is required as this function is called separately for sensors and attributes
        log_prefix = f"{self._name} # {sensor}"
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
                _LOGGER.debug("%s # Select selected tag: %s", log_prefix, tag)
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
            self.notify_scrape_exception()
            raise
