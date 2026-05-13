"""HTTP session manager with form authentication support."""
import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from homeassistant.const import (CONF_AUTHENTICATION, CONF_HEADERS,
                                 CONF_METHOD, CONF_NAME, CONF_PARAMS,
                                 CONF_PASSWORD, CONF_PAYLOAD, CONF_RESOURCE,
                                 CONF_TIMEOUT, CONF_USERNAME, CONF_VERIFY_SSL,
                                 HTTP_DIGEST_AUTHENTICATION)
from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import client_context, create_no_verify_ssl_context

from .const import (CONF_FORM_INPUT, CONF_FORM_INPUT_FILTER,
                    CONF_FORM_RESUBMIT_ERROR, CONF_FORM_SELECT,
                    CONF_FORM_SUBMIT, CONF_FORM_SUBMIT_ONCE,
                    CONF_FORM_VARIABLES, CONF_PARSER)
from .file import LoggingFileManager
from .form_auth import FormAuthConfig, FormAuthenticator
from .http import merge_url_with_params
from .scrape_context import ScrapeContext
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


class HttpSession:
    """HTTP session manager with authentication support.

    Uses a dedicated httpx.AsyncClient instead of the shared HA client.
    This allows httpx to manage cookies naturally via its built-in cookie jar,
    eliminating manual cookie extraction/passing.

    Delegates form-based authentication to a FormAuthenticator collaborator.
    """

    def __init__(
        self,
        config_name: str,
        hass: HomeAssistant,
        http_config: HttpConfig,
        file_manager: LoggingFileManager | None = None,
        form_authenticator: FormAuthenticator | None = None,
    ):
        """Initialize HTTP session."""
        self._config_name = config_name
        self._hass = hass
        self._http_config = http_config
        self._file_manager = file_manager
        self._form_authenticator = form_authenticator

        # Create dedicated httpx client with its own cookie jar.
        # Use HA's pre-warmed cached SSL context so CA certs are never loaded
        # on the event loop (homeassistant.util.ssl pre-warms the cache at
        # import time precisely to avoid blocking I/O here).
        ssl_ctx = client_context() if http_config.verify_ssl else create_no_verify_ssl_context()
        self._client = httpx.AsyncClient(
            verify=ssl_ctx,
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

        _LOGGER.debug("%s # HttpSession initialized", config_name)

    async def async_request(
        self,
        context: str,
        resource: str,
        method: str | None = None,
        request_data: Any = None,
        scrape_context: ScrapeContext | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request.

        Cookies are managed automatically by the dedicated httpx client.
        """
        variables = scrape_context.to_template_variables() if scrape_context else {}
        data = request_data or self._http_config.data_renderer(variables)
        method = method or self._http_config.method or "GET"
        headers = self._http_config.headers_renderer(variables)
        params = self._http_config.params_renderer(variables)

        return await self._execute_request(
            context=context,
            method=method,
            resource=resource,
            headers=headers,
            params=params,
            auth=self._auth,
            data=data,
        )

    async def _execute_request(
        self,
        context: str,
        method: str,
        resource: str,
        headers: dict,
        params: dict,
        auth: Any,
        data: Any = None,
    ) -> httpx.Response:
        """Core HTTP request with logging and error handling."""
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
                "auth": auth,
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
        if not self._form_authenticator:
            return None
        return await self._form_authenticator.ensure_authenticated(main_resource)

    def invalidate_auth(self):
        """Invalidate the current authentication so the form will be re-submitted.

        Clears the cookie jar when resubmission will happen, to prevent stale
        session cookies from interfering with fresh authentication. When
        resubmit_on_error is False, cookies are preserved since there is no
        way to re-establish the session.
        """
        if self._form_authenticator:
            self._form_authenticator.invalidate()
            if self._form_authenticator._should_submit:
                self._client.cookies.clear()
                _LOGGER.debug(
                    "%s # Cookies cleared for fresh authentication",
                    self._config_name,
                )

    @property
    def form_variables(self) -> dict[str, Any]:
        """Return variables scraped during form authentication."""
        if self._form_authenticator:
            return self._form_authenticator.form_variables
        return {}

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
            filename = f"{context}_{content_name}.txt"
            try:
                await self._hass.async_add_executor_job(
                    self._file_manager.write, filename, content
                )
                _LOGGER.debug(
                    "%s # %s written to file: %s",
                    self._config_name,
                    content_name,
                    filename,
                )
            except Exception as ex:
                _LOGGER.error(
                    "%s # Unable to write %s to file: %s. \nException: %s",
                    self._config_name,
                    content_name,
                    filename,
                    ex,
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

        # Create session first so FormAuthenticator can use its _execute_request
        session = HttpSession(
            config_name=config_name,
            hass=hass,
            http_config=http_config,
            file_manager=file_manager,
        )

        form_authenticator = FormAuthenticator(
            config_name=config_name,
            config=form_auth_config,
            execute_request=session._execute_request,
            file_log=session._async_file_log if file_manager else None,
        )
        session._form_authenticator = form_authenticator
        return session

    return HttpSession(
        config_name=config_name,
        hass=hass,
        http_config=http_config,
        file_manager=file_manager,
    )
