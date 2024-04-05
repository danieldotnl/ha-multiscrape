"""Form submit logic."""
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_RESOURCE

from .const import (
    CONF_FORM_SELECT,
    CONF_FORM_INPUT,
    CONF_FORM_INPUT_FILTER,
    CONF_FORM_SUBMIT_ONCE,
    CONF_FORM_RESUBMIT_ERROR,
)
from .file import LoggingFileManager
from .http import HttpWrapper


_LOGGER = logging.getLogger(__name__)


def create_form_submitter(config_name, config, hass, http, file_manager, parser):
    """Create a form submitter instance."""
    resource = config.get(CONF_RESOURCE)
    select = config.get(CONF_FORM_SELECT)
    input_values = config.get(CONF_FORM_INPUT)
    input_filter = config.get(CONF_FORM_INPUT_FILTER)
    resubmit_error = config.get(CONF_FORM_RESUBMIT_ERROR)
    submit_once = config.get(CONF_FORM_SUBMIT_ONCE)

    return FormSubmitter(
        config_name,
        hass,
        http,
        file_manager,
        resource,
        select,
        input_values,
        input_filter,
        submit_once,
        resubmit_error,
        parser,
    )


class FormSubmitter:
    """Class to take care of submitting a form."""

    def __init__(
        self,
        config_name,
        hass: HomeAssistant,
        http: HttpWrapper,
        file_manager: LoggingFileManager,
        form_resource,
        select,
        input_values,
        input_filter,
        submit_once,
        resubmit_error,
        parser,
    ):
        """Initialize FormSubmitter class."""
        _LOGGER.debug("%s # Initializing form submitter", config_name)
        self._config_name = config_name
        self._hass = hass
        self._http = http
        self._file_manager = file_manager
        self._form_resource = form_resource
        self._select = select
        self._input_values = input_values
        self._input_filter = input_filter
        self._submit_once = submit_once
        self._resubmit_error = resubmit_error
        self._parser = parser
        self._should_submit = True

    def notify_scrape_exception(self):
        """Make sure form is re-submitted after an exception."""
        if self._resubmit_error:
            _LOGGER.debug(
                "%s # Exception occurred while scraping, will try to resubmit the form next interval.",
                self._config_name,
            )
            self._should_submit = True

    async def async_submit(self, main_resource):
        """Submit the form."""
        if not self._should_submit:
            _LOGGER.debug("%s # Skip submitting form")
            return

        _LOGGER.debug("%s # Starting with form-submit", self._config_name)
        input_fields = {}
        action, method = None, None

        if self._select:
            if self._form_resource:
                page = await self._fetch_form_page(self._form_resource)
            else:
                page = await self._fetch_form_page(main_resource)
            form = await self._async_substract_form(page)

            input_fields = self._get_input_fields(form)
            for field in self._input_filter:
                input_fields.pop(field, None)

            action = form.get("action")
            method = form.get("method")

            _LOGGER.debug(
                "%s # Found form action %s and method %s",
                self._config_name,
                action,
                method,
            )
        else:
            _LOGGER.debug(
                "%s # Skip scraping form, assuming all input is given in config.",
                self._config_name,
            )

        input_fields.update(self._input_values)

        _LOGGER.debug(
            "%s # Merged input fields with input data in config. Result: %s",
            self._config_name,
            input_fields,
        )

        if not method:
            method = "POST"

        submit_resource = self._determine_submit_resource(action, main_resource)

        _LOGGER.debug("%s # Submitting the form", self._config_name)
        response = await self._http.async_request(
            "form_submit",
            submit_resource,
            method=method,
            request_data=input_fields,
        )
        _LOGGER.debug(
            "%s # Form seems to be submitted successfully (to be sure, use log_response and check file). Now continuing to retrieve target page.",
            self._config_name,
        )

        if self._submit_once:
            self._should_submit = False

        if not self._form_resource:
            return response.text
        else:
            return None

    def _determine_submit_resource(self, action, main_resource):
        resource = main_resource
        if action and self._form_resource:
            resource = urljoin(self._form_resource, action)
        elif action:
            resource = urljoin(main_resource, action)
        elif self._form_resource:
            resource = self._form_resource

        _LOGGER.debug(
            "%s # Determined the url to submit the form to: %s",
            self._config_name,
            resource,
        )
        return resource

    async def _fetch_form_page(self, resource):
        _LOGGER.debug(
            "%s # Requesting page with form from: %s",
            self._config_name,
            resource,
        )
        response = await self._http.async_request(
            "form_page",
            resource,
            "GET",
        )
        return response.text

    def _get_input_fields(self, form):
        _LOGGER.debug("%s # Finding all input fields in form", self._config_name)
        elements = form.findAll("input")
        input_fields = {
            element.get("name"): element.get("value") for element in elements
        }
        _LOGGER.debug(
            "%s # Found the following input fields: %s", self._config_name, input_fields
        )
        return input_fields

    async def _async_file_log(self, content_name, content):
        try:
            filename = f"{content_name}.txt"
            await self._hass.async_add_executor_job(
                self._file_manager.write, filename, content
            )
        except Exception as ex:
            _LOGGER.error(
                "%s # Unable to write BeautifulSoup form-page result to file: %s. \nException: %s",
                self._config_name,
                filename,
                ex,
            )
        _LOGGER.debug(
            "%s # The page with the form parsed by BeautifulSoup has been written to file: %s",
            self._config_name,
            filename,
        )

    async def _async_substract_form(self, page):
        try:
            _LOGGER.debug(
                "%s # Parse page with form with BeautifulSoup parser %s",
                self._config_name,
                self._parser,
            )
            soup = BeautifulSoup(page, self._parser)
            soup.prettify()
            if self._file_manager:
                await self._async_file_log("form_page_soup", soup)

            _LOGGER.debug(
                "%s # Try to find form with selector %s",
                self._config_name,
                self._select,
            )
            form = soup.select_one(self._select)

            if not form:
                raise ValueError("Could not find form")

            _LOGGER.debug("%s # Form looks like this: \n%s", self._config_name, form)
            return form

        except IndexError as exception:
            _LOGGER.info(
                "%s # Unable to get the form from the page: %s",
                self._config_name,
                exception,
            )
            raise
