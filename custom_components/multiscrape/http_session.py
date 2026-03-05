"""Unified HTTP session manager with authentication support."""
import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from homeassistant.const import (CONF_AUTHENTICATION, CONF_HEADERS,
                                 CONF_METHOD, CONF_NAME, CONF_PARAMS,
                                 CONF_PASSWORD, CONF_PAYLOAD, CONF_RESOURCE,
                                 CONF_TIMEOUT, CONF_USERNAME, CONF_VERIFY_SSL,
                                 HTTP_DIGEST_AUTHENTICATION)
from homeassistant.core import HomeAssistant

from .const import (CONF_FORM_INPUT, CONF_FORM_INPUT_FILTER,
                    CONF_FORM_RESUBMIT_ERROR, CONF_FORM_SELECT,
                    CONF_FORM_SUBMIT, CONF_FORM_SUBMIT_ONCE,
                    CONF_FORM_VARIABLES, CONF_PARSER)
from .file import LoggingFileManager
from .http import merge_url_with_params
from .scraper import create_scraper
from .selector import Selector
from .util import create_dict_renderer, create_renderer

_LOGGER = logging.getLogger(__name__)


@dataclass
class HttpConfig:
    """HTTP client configuration."""

    verify_ssl: bool = True
    timeout: int = 10
    method: str = "GET"
    username: str | None = None
    password: str | None = None
    auth_type: str | None = None
    headers_renderer: Callable = field(default_factory=lambda: lambda variables={}, parse_result=None: {})
    params_renderer: Callable = field(default_factory=lambda: lambda variables={}, parse_result=None: {})
    data_renderer: Callable = field(default_factory=lambda: lambda variables={}, parse_result=None: None)


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


class HttpSession:
    """Unified HTTP session manager with authentication support.

    Uses a dedicated httpx.AsyncClient instead of the shared HA client.
    This allows httpx to manage cookies naturally via its built-in cookie jar,
    eliminating manual cookie extraction/passing.
    """

    def __init__(
        self,
        config_name: str,
        hass: HomeAssistant,
        http_config: HttpConfig,
        file_manager: LoggingFileManager | None = None,
        form_auth_config: FormAuthConfig | None = None,
    ):
        """Initialize HTTP session."""
        self._config_name = config_name
        self._hass = hass
        self._http_config = http_config
        self._file_manager = file_manager
        self._form_auth_config = form_auth_config

        # Create dedicated httpx client with its own cookie jar
        self._client = httpx.AsyncClient(
            verify=http_config.verify_ssl,
            timeout=http_config.timeout,
            follow_redirects=True,
        )

        # Set HTTP auth if configured
        self._auth = None
        if http_config.username and http_config.password:
            if http_config.auth_type == HTTP_DIGEST_AUTHENTICATION:
                self._auth = httpx.DigestAuth(http_config.username, http_config.password)
            else:
                self._auth = (http_config.username, http_config.password)
            _LOGGER.debug("%s # Authentication configuration processed", config_name)

        # Form auth state
        self._should_submit = True
        self._form_variables: dict[str, Any] = {}

        _LOGGER.debug("%s # HttpSession initialized", config_name)

    async def async_request(
        self,
        context: str,
        resource: str,
        method: str | None = None,
        request_data: Any = None,
        variables: dict = {},
    ) -> httpx.Response:
        """Execute an HTTP request.

        Cookies are managed automatically by the dedicated httpx client.
        """
        data = request_data or self._http_config.data_renderer(variables)
        method = method or self._http_config.method or "GET"
        headers = self._http_config.headers_renderer(variables)
        params = self._http_config.params_renderer(variables)

        merged_resource = merge_url_with_params(resource, params)

        _LOGGER.debug(
            "%s # Executing %s-request with a %s to url: %s with headers: %s.",
            self._config_name,
            context,
            method,
            merged_resource,
            headers,
        )
        if self._file_manager:
            await asyncio.gather(
                self._async_file_log("request_headers", context, headers),
                self._async_file_log("request_body", context, data),
            )

        response = None
        try:
            request_params = {
                "method": method,
                "url": merged_resource,
                "headers": headers,
                "auth": self._auth,
            }

            if data is not None:
                if isinstance(data, dict):
                    request_params["data"] = data
                else:
                    request_params["content"] = data

            response = await self._client.request(**request_params)

            _LOGGER.debug(
                "%s # Response status code received: %s",
                self._config_name,
                response.status_code,
            )
            if self._file_manager:
                await asyncio.gather(
                    self._async_file_log("response_headers", context, response.headers),
                    self._async_file_log("response_body", context, response.text),
                )

            if 400 <= response.status_code <= 599:
                response.raise_for_status()
            return response
        except httpx.TimeoutException as ex:
            _LOGGER.debug(
                "%s # Timeout error while executing %s request to url: %s.\n Error message:\n %s",
                self._config_name,
                method,
                merged_resource,
                repr(ex),
            )
            await self._handle_request_exception(context, response)
            raise
        except httpx.RequestError as ex:
            _LOGGER.debug(
                "%s # Request error while executing %s request to url: %s.\n Error message:\n %s",
                self._config_name,
                method,
                merged_resource,
                repr(ex),
            )
            await self._handle_request_exception(context, response)
            raise
        except Exception as ex:
            _LOGGER.debug(
                "%s # Error executing %s request to url: %s.\n Error message:\n %s",
                self._config_name,
                method,
                merged_resource,
                repr(ex),
            )
            await self._handle_request_exception(context, response)
            raise

    async def ensure_authenticated(self, main_resource: str) -> str | None:
        """Ensure session is authenticated via form submission if configured.

        Returns form response text when form uses the main resource (no separate form_resource),
        or None when form has its own resource (main page still needs fetching).
        Returns None when no form auth is configured.
        """
        if not self._form_auth_config:
            return None

        if not self._should_submit:
            _LOGGER.debug("%s # Skip submitting form", self._config_name)
            return None

        _LOGGER.debug("%s # Starting with form-submit", self._config_name)
        form_cfg = self._form_auth_config
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
        else:
            return None

    async def _form_request(
        self,
        context: str,
        resource: str,
        method: str = "GET",
        request_data: Any = None,
    ) -> httpx.Response:
        """Execute an HTTP request using form auth config renderers."""
        form_cfg = self._form_auth_config
        headers = form_cfg.headers_renderer()
        params = form_cfg.params_renderer()

        merged_resource = merge_url_with_params(resource, params)

        _LOGGER.debug(
            "%s # Executing %s-request with a %s to url: %s with headers: %s.",
            self._config_name,
            context,
            method,
            merged_resource,
            headers,
        )
        if self._file_manager:
            await asyncio.gather(
                self._async_file_log("request_headers", context, headers),
                self._async_file_log("request_body", context, request_data),
            )

        request_params = {
            "method": method,
            "url": merged_resource,
            "headers": headers,
            "auth": form_cfg.auth,
        }

        if request_data is not None:
            if isinstance(request_data, dict):
                request_params["data"] = request_data
            else:
                request_params["content"] = request_data

        response = await self._client.request(**request_params)

        _LOGGER.debug(
            "%s # Response status code received: %s",
            self._config_name,
            response.status_code,
        )
        if self._file_manager:
            await asyncio.gather(
                self._async_file_log("response_headers", context, response.headers),
                self._async_file_log("response_body", context, response.text),
            )

        if 400 <= response.status_code <= 599:
            response.raise_for_status()
        return response

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
            self._form_auth_config.parser,
        )
        soup = BeautifulSoup(page, self._form_auth_config.parser)
        soup.prettify()
        if self._file_manager:
            await self._async_file_log("form_page_soup", "form", soup)

        _LOGGER.debug(
            "%s # Try to find form with selector %s",
            self._config_name,
            self._form_auth_config.select,
        )
        form = soup.select_one(self._form_auth_config.select)

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
        form_resource = self._form_auth_config.resource
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

    def notify_scrape_exception(self):
        """Re-submit form after a scrape exception if configured."""
        if self._form_auth_config and self._form_auth_config.resubmit_on_error:
            _LOGGER.debug(
                "%s # Exception occurred while scraping, will try to resubmit the form next interval.",
                self._config_name,
            )
            self._should_submit = True

    @property
    def form_variables(self) -> dict[str, Any]:
        """Return variables scraped during form authentication."""
        return self._form_variables

    async def async_close(self):
        """Close the dedicated HTTP client."""
        await self._client.aclose()
        _LOGGER.debug("%s # HttpSession closed", self._config_name)

    async def _handle_request_exception(self, context, response):
        """Log response details on request exception."""
        if response is None:
            return
        try:
            if self._file_manager:
                await asyncio.gather(
                    self._async_file_log("response_headers_error", context, response.headers),
                    self._async_file_log("response_body_error", context, response.text),
                )
        except Exception as exc:
            _LOGGER.debug(
                "%s # Unable to write headers and/or body to file during handling of exception.\n Error message:\n %s",
                self._config_name,
                repr(exc),
            )

    async def _async_file_log(self, content_name, context, content):
        """Write content to a file if content is not None."""
        if content is not None:
            try:
                filename = f"{context}_{content_name}.txt"
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


def create_http_session(config_name, conf, hass, file_manager):
    """Create an HttpSession instance from configuration."""
    http_config = HttpConfig(
        verify_ssl=conf.get(CONF_VERIFY_SSL, True),
        timeout=conf.get(CONF_TIMEOUT, 10),
        method=conf.get(CONF_METHOD, "GET"),
        username=conf.get(CONF_USERNAME),
        password=conf.get(CONF_PASSWORD),
        auth_type=conf.get(CONF_AUTHENTICATION),
        headers_renderer=create_dict_renderer(hass, conf.get(CONF_HEADERS)),
        params_renderer=create_dict_renderer(hass, conf.get(CONF_PARAMS)),
        data_renderer=create_renderer(hass, conf.get(CONF_PAYLOAD), "request payload"),
    )

    form_auth_config = None
    form_submit_config = conf.get(CONF_FORM_SUBMIT)
    if form_submit_config:
        # Build form auth renderers from form_submit config (has its own HTTP_SCHEMA fields)
        form_auth = None
        form_username = form_submit_config.get(CONF_USERNAME)
        form_password = form_submit_config.get(CONF_PASSWORD)
        if form_username and form_password:
            form_auth_type = form_submit_config.get(CONF_AUTHENTICATION)
            if form_auth_type == HTTP_DIGEST_AUTHENTICATION:
                form_auth = httpx.DigestAuth(form_username, form_password)
            else:
                form_auth = (form_username, form_password)

        # Build form variables selectors
        scraper = None
        variables_selectors = {}
        variables = form_submit_config.get(CONF_FORM_VARIABLES)
        if variables:
            scraper = create_scraper(config_name, form_submit_config, hass, file_manager)
            for variables_conf in variables:
                variables_selectors[variables_conf.get(CONF_NAME)] = Selector(hass, variables_conf)

        form_auth_config = FormAuthConfig(
            resource=form_submit_config.get(CONF_RESOURCE),
            select=form_submit_config.get(CONF_FORM_SELECT),
            input_values=form_submit_config.get(CONF_FORM_INPUT),
            input_filter=form_submit_config.get(CONF_FORM_INPUT_FILTER, []),
            submit_once=form_submit_config.get(CONF_FORM_SUBMIT_ONCE, False),
            resubmit_on_error=form_submit_config.get(CONF_FORM_RESUBMIT_ERROR, True),
            variables_selectors=variables_selectors,
            scraper=scraper,
            parser=conf.get(CONF_PARSER, "lxml"),
            headers_renderer=create_dict_renderer(hass, form_submit_config.get(CONF_HEADERS)),
            params_renderer=create_dict_renderer(hass, form_submit_config.get(CONF_PARAMS)),
            data_renderer=create_renderer(hass, form_submit_config.get(CONF_PAYLOAD), "form request payload"),
            method=form_submit_config.get(CONF_METHOD),
            auth=form_auth,
        )

    return HttpSession(
        config_name=config_name,
        hass=hass,
        http_config=http_config,
        file_manager=file_manager,
        form_auth_config=form_auth_config,
    )
