"""HTTP request related functionality."""
import asyncio
import logging
from collections.abc import Callable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
from homeassistant.const import (CONF_AUTHENTICATION, CONF_HEADERS,
                                 CONF_METHOD, CONF_PARAMS, CONF_PASSWORD,
                                 CONF_PAYLOAD, CONF_TIMEOUT, CONF_USERNAME,
                                 CONF_VERIFY_SSL, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.helpers.httpx_client import get_async_client

from .util import create_dict_renderer, create_renderer

_LOGGER = logging.getLogger(__name__)


def create_http_wrapper(config_name, config, hass, file_manager):
    """Create a http wrapper instance."""
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    auth_type = config.get(CONF_AUTHENTICATION)
    timeout = config.get(CONF_TIMEOUT)
    headers = config.get(CONF_HEADERS)
    params = config.get(CONF_PARAMS)
    payload = config.get(CONF_PAYLOAD)
    method = config.get(CONF_METHOD)

    client = get_async_client(hass, verify_ssl)
    http = HttpWrapper(
        config_name,
        hass,
        client,
        file_manager,
        timeout,
        method,
        params_renderer=create_dict_renderer(hass, params),
        headers_renderer=create_dict_renderer(hass, headers),
        data_renderer=create_renderer(hass, payload),
    )
    if username and password:
        http.set_authentication(username, password, auth_type)
    return http


class HttpWrapper:
    """Class to wrap a httpx request."""

    def __init__(
        self,
        config_name,
        hass,
        client,
        file_manager,
        timeout,
        method: str = None,
        params_renderer: Callable = None,
        headers_renderer: Callable = None,
        data_renderer: Callable = None,
    ):
        """Initialize HttpWrapper."""
        _LOGGER.debug("%s # Initializing http wrapper", config_name)
        self._client = client
        self._file_manager = file_manager
        self._config_name = config_name
        self._timeout = timeout
        self._hass = hass
        self._auth = None
        self._method = method
        self._params_renderer = params_renderer
        self._headers_renderer = headers_renderer
        self._data_renderer = data_renderer

    def set_authentication(self, username, password, auth_type):
        """Set http authentication."""
        if auth_type == HTTP_DIGEST_AUTHENTICATION:
            self._auth = httpx.DigestAuth(username, password)
        else:
            self._auth = (username, password)
        _LOGGER.debug(
            "%s # Authentication configuration processed", self._config_name)

    async def async_request(self, context, resource, method=None, request_data=None, cookies=None, variables: dict = {}):
        """Execute a HTTP request."""
        data = request_data or self._data_renderer(variables)
        method = method or self._method or "GET"
        headers = self._headers_renderer(variables)
        params = self._params_renderer(variables)

        # Merging params in multiscrape since httpx doesn't do it anymore: https://github.com/encode/httpx/issues/3433
        merged_resource = merge_url_with_params(resource, params)

        _LOGGER.debug(
            "%s # Executing %s-request with a %s to url: %s with headers: %s and cookies: %s.",
            self._config_name,
            context,
            method,
            merged_resource,
            headers,
            cookies
        )
        if self._file_manager:
            task1 = self._async_file_log("request_headers", context, headers)
            task2 = self._async_file_log("request_body", context, data)
            task3 = self._async_file_log("request_cookies", context, cookies)
            await asyncio.gather(task1, task2, task3)

        response = None

        try:
            response = await self._client.request(
                method,
                merged_resource,
                headers=headers,
                auth=self._auth,
                data=data,
                timeout=self._timeout,
                follow_redirects=True,
                cookies=cookies
            )

            _LOGGER.debug(
                "%s # Response status code received: %s",
                self._config_name,
                response.status_code,
            )
            if self._file_manager:
                task1 = self._async_file_log(
                    "response_headers", context, response.headers
                )
                task2 = self._async_file_log(
                    "response_body", context, response.text)
                task3 = self._async_file_log(
                    "response_cookies", context, response.cookies)
                await asyncio.gather(task1, task2, task3)

            # bit of a hack since httpx also raises an exception for redirects: https://github.com/encode/httpx/blob/c6c8cb1fe2da9380f8046a19cdd5aade586f69c8/CHANGELOG.md#0200-13th-october-2021
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

    async def _handle_request_exception(self, context, response):
        try:
            if self._file_manager:
                task1 = self._async_file_log(
                    "response_headers_error", context, response.headers
                )
                task2 = self._async_file_log(
                    "response_body_error", context, response.text
                )
                task3 = self._async_file_log(
                    "response_cookies_error", context, response.cookies
                )
                await asyncio.gather(task1, task2, task3)
        except Exception as exc:
            _LOGGER.debug(
                "%s # Unable to write headers, cookies and/or body to file during handling of exception.\n Error message:\n %s",
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


def merge_url_with_params(url, params):
    """Merge URL with parameters."""
    if not params:
        return url

    url_parts = list(urlparse(url))
    query = parse_qs(url_parts[4])
    query.update(params)
    url_parts[4] = urlencode(query, doseq=True)
    try:
        return urlunparse(url_parts)
    except Exception as ex:
        raise ValueError(f"Failed to merge URL with parameters: {ex}") from ex
