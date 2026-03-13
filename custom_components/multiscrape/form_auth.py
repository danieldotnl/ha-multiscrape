"""Form-based authentication handler."""
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


@dataclass
class FormAuthConfig:
    """Configuration for form-based authentication."""

    resource: str | None = None
    select: str | None = None
    input_values: dict[str, str] | None = None
    input_filter: list[str] = field(default_factory=list)
    submit_once: bool = False
    resubmit_on_error: bool = True
    variables_selectors: dict[str, Any] = field(default_factory=dict)
    scraper: Any = None
    parser: str = "lxml"
    headers_renderer: Callable = field(default_factory=lambda: lambda variables={}, parse_result=None: {})
    params_renderer: Callable = field(default_factory=lambda: lambda variables={}, parse_result=None: {})
    data_renderer: Callable = field(default_factory=lambda: lambda variables={}, parse_result=None: None)
    method: str | None = None
    auth: Any = None


class FormAuthenticator:
    """Handles form-based authentication within an HTTP session.

    Receives an execute_request callback from HttpSession to make HTTP requests
    through the shared httpx.AsyncClient, preserving cookie sharing.
    """

    def __init__(
        self,
        config_name: str,
        config: FormAuthConfig,
        execute_request: Callable,
        file_log: Callable | None = None,
    ):
        """Initialize form authenticator."""
        self._config_name = config_name
        self._config = config
        self._execute_request = execute_request
        self._file_log = file_log
        self._should_submit: bool = True
        self._form_variables: dict[str, Any] = {}

    @property
    def form_variables(self) -> dict[str, Any]:
        """Return variables scraped during form authentication."""
        return self._form_variables

    async def ensure_authenticated(self, main_resource: str) -> str | None:
        """Ensure session is authenticated via form submission if configured.

        Returns form response text when form uses the main resource (no separate form_resource),
        or None when form has its own resource (main page still needs fetching).
        """
        if not self._should_submit:
            _LOGGER.debug("%s # Skip submitting form", self._config_name)
            return None

        _LOGGER.debug("%s # Starting with form-submit", self._config_name)
        form_cfg = self._config
        input_fields = {}
        action, method = None, None

        if form_cfg.select:
            form_resource = form_cfg.resource or main_resource
            page = await self._fetch_form_page(form_resource)
            form = await self._extract_form(page)

            input_fields = self._get_input_fields(form)
            for field_name in form_cfg.input_filter:
                input_fields.pop(field_name, None)

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

        if form_cfg.input_values is not None:
            input_fields.update(form_cfg.input_values)
            _LOGGER.debug(
                "%s # Merged input fields with input data in config. Result: %s",
                self._config_name,
                input_fields,
            )

        payload = input_fields if input_fields else None

        if not method:
            method = "POST"

        submit_resource = self._determine_submit_resource(action, main_resource)

        _LOGGER.debug("%s # Submitting the form", self._config_name)
        response = await self._form_request(
            "form_submit",
            submit_resource,
            method=method,
            request_data=payload,
        )
        _LOGGER.debug(
            "%s # Form seems to be submitted successfully (to be sure, use log_response and check file). Now continuing to retrieve target page.",
            self._config_name,
        )

        if form_cfg.submit_once:
            self._should_submit = False

        # Scrape variables from form response if configured
        if form_cfg.scraper:
            await form_cfg.scraper.set_content(response.text)
            self._form_variables = {}
            for variable_key in form_cfg.variables_selectors:
                self._form_variables[variable_key] = form_cfg.scraper.scrape(
                    form_cfg.variables_selectors[variable_key], variable_key
                )

        if not form_cfg.resource:
            return response.text
        return None

    def invalidate(self):
        """Mark session as invalid so the form will be re-submitted next interval."""
        if self._config.resubmit_on_error:
            _LOGGER.debug(
                "%s # Session invalidated, will re-submit the form next interval.",
                self._config_name,
            )
            self._should_submit = True

    async def _form_request(
        self,
        context: str,
        resource: str,
        method: str = "GET",
        request_data: Any = None,
    ) -> httpx.Response:
        """Execute an HTTP request using form auth config renderers."""
        form_cfg = self._config
        headers = form_cfg.headers_renderer()
        params = form_cfg.params_renderer()

        return await self._execute_request(
            context=context,
            method=method,
            resource=resource,
            headers=headers,
            params=params,
            auth=form_cfg.auth,
            data=request_data,
        )

    async def _fetch_form_page(self, resource: str) -> str:
        """Fetch the page containing the form."""
        _LOGGER.debug(
            "%s # Requesting page with form from: %s",
            self._config_name,
            resource,
        )
        response = await self._form_request("form_page", resource, "GET")
        return response.text

    async def _extract_form(self, page: str):
        """Parse page HTML and extract the form element."""
        _LOGGER.debug(
            "%s # Parse page with form with BeautifulSoup parser %s",
            self._config_name,
            self._config.parser,
        )
        soup = BeautifulSoup(page, self._config.parser)
        if self._file_log:
            await self._file_log("form_page_soup", "form", soup.prettify())

        _LOGGER.debug(
            "%s # Try to find form with selector %s",
            self._config_name,
            self._config.select,
        )
        form = soup.select_one(self._config.select)

        if not form:
            raise ValueError("Could not find form")

        _LOGGER.debug("%s # Form looks like this: \n%s", self._config_name, form)
        return form

    def _get_input_fields(self, form) -> dict:
        """Extract input field names and values from a form element."""
        _LOGGER.debug("%s # Finding all input fields in form", self._config_name)
        elements = form.find_all("input")
        input_fields = {
            element.get("name"): element.get("value")
            for element in elements
            if element.get("name") is not None
        }
        _LOGGER.debug(
            "%s # Found the following input fields: %s", self._config_name, input_fields
        )
        return input_fields

    def _determine_submit_resource(self, action: str | None, main_resource: str) -> str:
        """Determine the URL to submit the form to."""
        form_resource = self._config.resource
        resource = main_resource
        if action and form_resource:
            resource = urljoin(form_resource, action)
        elif action:
            resource = urljoin(main_resource, action)
        elif form_resource:
            resource = form_resource

        _LOGGER.debug(
            "%s # Determined the url to submit the form to: %s",
            self._config_name,
            resource,
        )
        return resource
