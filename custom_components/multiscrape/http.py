import logging

import httpx
from homeassistant.const import HTTP_DIGEST_AUTHENTICATION

_LOGGER = logging.getLogger(__name__)


class HttpWrapper:
    def __init__(self, config_name, hass, client, file_manager, timeout):
        self._client = client
        self._file_manager = file_manager
        self._config_name = config_name
        self._timeout = timeout
        self._hass = hass
        self._auth = None

    def set_authentication(self, username, password, auth_type):
        if auth_type == HTTP_DIGEST_AUTHENTICATION:
            self._auth = httpx.DigestAuth(username, password)
        else:
            self._auth = (username, password)
        _LOGGER.debug("%s # Authentication configuration processed", self._config_name)

    async def async_request(
        self, context, method, resource, headers, params, request_data
    ):
        _LOGGER.debug(
            "%s # Executing %s-request with a %s to url: %s.",
            self._config_name,
            context,
            method,
            resource,
        )
        try:
            response = await self._client.request(
                method,
                resource,
                headers=headers,
                params=params,
                auth=self._auth,
                data=request_data,
                timeout=self._timeout,
            )

            _LOGGER.debug(
                "%s # Response status code received: %s",
                self._config_name,
                response.status_code,
            )
            if self._file_manager:
                await self._async_file_log(
                    "response_headers", context, response.headers
                )
                await self._async_file_log("response_body", context, response.text)

            return response

        except Exception as ex:
            _LOGGER.error(
                "%s # Error executing %s request to url: %s.\n Error message:\n %s",
                self._name,
                method,
                resource,
                repr(ex),
            )
            raise

    async def _async_file_log(self, content_name, context, content):
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
