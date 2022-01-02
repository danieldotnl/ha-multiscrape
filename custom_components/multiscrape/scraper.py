"""Support for multiscrape requests."""
import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from homeassistant.helpers.httpx_client import get_async_client

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
        method,
        resource,
        auth,
        headers,
        params,
        data,
        verify_ssl,
        parser,
        form_submit_config,
        timeout=DEFAULT_TIMEOUT,
    ):
        """Initialize the data object."""
        self._hass = hass
        self._method = method
        self._resource = resource
        self._auth = auth
        self._headers = headers
        self._params = params
        self._request_data = data
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._parser = parser
        self._async_client = None
        self._form_submit_config = form_submit_config
        self.data = None
        self.last_exception = None
        self.headers = None
        self._skip_form = False

        if form_submit_config:
            self._form_resource = self._form_submit_config.get(CONF_FORM_RESOURCE)
            self._form_select = self._form_submit_config.get(CONF_FORM_SELECT)
            self._form_input = self._form_submit_config.get(CONF_FORM_INPUT)
            self._form_submit_once = self._form_submit_config.get(CONF_FORM_SUBMIT_ONCE)
            self._form_resubmit_error = self._form_submit_config.get(
                CONF_FORM_RESUBMIT_ERROR
            )

    def notify_scrape_exception(self):
        if self._form_submit_config and self._form_resubmit_error:
            self._skip_form = False

    def set_url(self, url):
        """Set url."""
        self._resource = url

    async def async_update(self, log_errors=True):
        """Get the latest data from REST service with provided method."""
        if not self._async_client:
            self._async_client = get_async_client(
                self._hass, verify_ssl=self._verify_ssl
            )

        if self._form_submit_config is None or self._skip_form:
            if self._skip_form:
                _LOGGER.debug("Skip submitting form for resource: %s", self._resource)
            await self._async_update_data()

        else:
            page = await self._async_get_form_page()
            form = self._get_form_data(page)

            if not form:
                await self._async_update_data()
            else:
                form_action = form[0]
                form_method = form[1]
                form_data = form[2]

                submit_resource = self._determine_submit_resource(form_action)
                form_data.update(self._form_input)

                result = await self._submit_form(
                    submit_resource, form_method, form_data
                )

                if not self._form_resource:
                    self.data = result.data
                else:
                    await self._async_update_data()

        try:
            self.soup = BeautifulSoup(self.data, self._parser)
            self.soup.prettify()
        except Exception as e:
            _LOGGER.error("Unable to parse response.")
            _LOGGER.debug("Exception parsing resonse: %s", e)

    async def _submit_form(self, resource, method, form_data, log_errors=True):

        if not method:
            method = "POST"

        _LOGGER.debug("Submitting form data %s to %s", form_data, resource)
        try:
            response = await self._async_client.request(
                method,
                resource,
                headers=self._headers,
                params=self._params,
                auth=self._auth,
                data=form_data,
                timeout=self._timeout,
            )

            if self._form_submit_once:
                self._skip_form = True
            return response
        except httpx.RequestError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error fetching data: %s failed with %s", self._resource, ex
                )

    async def _async_update_data(self, log_errors=True):
        _LOGGER.debug("Updating from %s", self._resource)
        try:
            response = await self._async_client.request(
                self._method,
                self._resource,
                headers=self._headers,
                params=self._params,
                auth=self._auth,
                data=self._request_data,
                timeout=self._timeout,
            )
            self.data = response.text
            self.headers = response.headers
        except httpx.RequestError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error fetching data: %s failed with %s", self._resource, ex
                )
            self.last_exception = ex
            self.data = None
            self.headers = None

    def _determine_submit_resource(self, action):
        if action and self._form_resource:
            return urljoin(self._form_resource, action)
        if action:
            return urljoin(self._resource, action)
        if self._form_resource:
            return self._form_resource
        return self._resource

    def _get_form_data(self, html):

        try:
            soup = BeautifulSoup(html, self._parser)
            form = soup.select(self._form_select)[0]
            if not form:
                return
            elements = form.findAll("input")
            formdata = dict(
                (element.get("name"), element.get("value")) for element in elements
            )

            action = form.get("action")
            method = form.get("method")

            return (action, method, formdata)

        except IndexError as exception:
            _LOGGER.info(
                "Unable to extract form data from %s. Skipping form submit and continuing.",
                self._form_resource,
            )
            _LOGGER.debug("Exception: %s", exception)
            return

    async def _async_get_form_page(self, log_errors=True):

        resource = self._form_resource if self._form_resource else self._resource

        _LOGGER.debug("Updating from %s", resource)
        try:
            return await self._async_client.request(
                "GET",
                resource,
                headers=self._headers,
                params=self._params,
                auth=self._auth,
                data=self._request_data,
                timeout=self._timeout,
            )

        except httpx.RequestError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error fetching form resource: %s failed with %s",
                    self._resource,
                    ex,
                )

    def scrape(self, selector):
        try:
            if selector.just_value:
                _LOGGER.debug("Applying value_template only.")
                return selector.value_template.async_render_with_possible_json_value(
                    self.data, None
                )

            if selector.is_list:
                tags = self.soup.select(selector.list)
                if selector.attribute is not None:
                    values = [tag[selector.attribute] for tag in tags]
                else:
                    values = [tag.text for tag in tags]
                value = ",".join(values)

            else:
                if selector.attribute is not None:
                    value = self.soup.select(selector.element)[selector.index][
                        selector.attribute
                    ]
                else:
                    tag = self.soup.select(selector.element)[selector.index]
                    if tag.name in ("style", "script", "template"):
                        value = tag.string
                    else:
                        value = tag.text

            if value is not None and selector.value_template is not None:
                value = selector.value_template.async_render(
                    variables={"value": value}, parse_result=False
                )

            return value
        except Exception:
            self.notify_scrape_exception()
            raise
