"""Coordinator class for multiscrape integration."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

import httpx
from homeassistant.const import (CONF_RESOURCE, CONF_RESOURCE_TEMPLATE,
                                 CONF_SCAN_INTERVAL,
                                 EVENT_HOMEASSISTANT_STARTED)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator, event)
from homeassistant.util.dt import utcnow

from .const import CONF_MAX_RETRIES, DOMAIN, MAX_RETRIES, RETRY_DELAY_SECONDS
from .file import LoggingFileManager
from .http_session import HttpSession
from .scrape_context import ScrapeContext
from .scraper import Scraper
from .util import create_renderer

_LOGGER = logging.getLogger(__name__)
# we don't want to go with the default 15 seconds defined in helpers/entity_component
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)


def create_content_request_manager(
    config_name, config, hass: HomeAssistant, session
):
    """Create a content request manager instance."""
    _LOGGER.debug("%s # Creating ContentRequestManager", config_name)
    resource = config.get(CONF_RESOURCE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)

    if resource_template is not None:
        resource_renderer = create_renderer(hass, resource_template, "resource URL template")
    else:
        resource_renderer = create_renderer(hass, resource, "resource URL")
    return ContentRequestManager(config_name, session, resource_renderer)


class ContentRequestManager:
    """Responsible for orchestrating all requests required to retrieve the desired content."""

    def __init__(
        self,
        config_name: str,
        session: HttpSession,
        resource_renderer: Callable,
    ) -> None:
        """Initialize ContentRequestManager."""
        self._config_name = config_name
        self._session = session
        self._resource_renderer = resource_renderer

    async def get_content(self, force_reauth: bool = False) -> str:
        """Retrieve the content of a url and first submit a form if required."""
        if force_reauth:
            self._session.invalidate_auth()

        resource = self._resource_renderer()

        try:
            result = await self._session.ensure_authenticated(resource)
            if result:
                _LOGGER.debug(
                    "%s # Using response from form-submit as content for scraping.",
                    self._config_name,
                )
                return result
        except httpx.HTTPStatusError as ex:
            if ex.response.status_code in (401, 403):
                _LOGGER.error(
                    "%s # Authentication rejected with HTTP %s. "
                    "Not falling through to target page as data would be unreliable.\n%s",
                    self._config_name,
                    ex.response.status_code,
                    ex,
                )
                raise
            _LOGGER.error(
                "%s # HTTP error during form-submit (status %s). "
                "Will continue trying to scrape target page.\n%s",
                self._config_name,
                ex.response.status_code,
                ex,
            )
        except Exception as ex:
            _LOGGER.error(
                "%s # Exception in form-submit feature. Will continue trying to scrape target page.\n%s",
                self._config_name,
                ex,
            )

        scrape_ctx = ScrapeContext(form_variables=self._session.form_variables)
        response = await self._session.async_request(
            "page", resource, scrape_context=scrape_ctx
        )
        return response.text

    @property
    def form_variables(self):
        """Return the form variables."""
        return self._session.form_variables


def create_multiscrape_coordinator(
    config_name, conf, hass, request_manager, file_manager, scraper
):
    """Create a multiscrape coordinator instance."""
    _LOGGER.debug("%s # Creating coordinator", config_name)

    scan_interval = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    max_retries = conf.get(CONF_MAX_RETRIES, MAX_RETRIES)

    return MultiscrapeDataUpdateCoordinator(
        config_name,
        hass,
        request_manager,
        file_manager,
        scraper,
        scan_interval,
        max_retries,
    )


class MultiscrapeDataUpdateCoordinator(TimestampDataUpdateCoordinator[None]):
    """Multiscrape coordinator class."""

    def __init__(
        self,
        config_name,
        hass: HomeAssistant,
        request_manager: ContentRequestManager,
        file_manager: LoggingFileManager,
        scraper: Scraper,
        update_interval: timedelta | None,
        max_retries: int = MAX_RETRIES,
    ):
        """Initialize the coordinator."""
        self._config_name = config_name
        self._request_manager = request_manager
        self._file_manager = file_manager
        self._scraper = scraper
        self._update_interval = update_interval
        self._max_retries = max_retries
        self.update_error = False
        self._resource = None
        self._retry_count: int = 0
        self._retry_unsub: CALLBACK_TYPE | None = None
        self._force_reauth: bool = False

        if self._update_interval == timedelta(seconds=0):
            self._update_interval = None

        # Best effort: the schema default means a config setting max_retries to
        # the default value is indistinguishable from one not setting it at all.
        if self._update_interval is not None and max_retries != MAX_RETRIES:
            _LOGGER.warning(
                "%s # max_retries is only used when scan_interval is 0 and will be ignored",
                self._config_name,
            )

        _LOGGER.debug(
            "%s # Scan interval is %s", self._config_name, self._update_interval
        )

        if self._update_interval and self._update_interval > timedelta(days=1):
            _LOGGER.warning(
                "%s # Scan interval is very long: %s. This may cause delays in data updates.",
                self._config_name,
                self._update_interval,
            )

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=self._update_interval
        )

        async def _on_hass_start(_: Event) -> None:
            """Trigger scrape on startup."""
            if self.update_interval and self.update_interval > timedelta(0):
                _LOGGER.debug("%s # Home assistant started, triggering scrape on startup", self._config_name)
                await self.async_refresh()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_hass_start)

    def request_reauth(self) -> None:
        """Flag that re-authentication is needed on the next update cycle."""
        self._force_reauth = True

    async def _async_update_data(self) -> None:
        # Any run supersedes a pending retry, including a manually triggered one.
        self._async_cancel_retry()
        await self._prepare_new_run()

        try:
            response = await self._request_manager.get_content(
                force_reauth=self._force_reauth
            )
            self._force_reauth = False
            await self._scraper.set_content(response)
            _LOGGER.debug(
                "%s # Data successfully refreshed. Sensors will now start scraping to update.",
                self._config_name,
            )
            self._retry_count = 0

        except Exception as ex:
            self._force_reauth = True
            _LOGGER.error(
                "%s # Updating failed with exception: %s",
                self._config_name,
                ex,
            )
            self._scraper.reset()
            self.update_error = True
            if self._update_interval is None:
                self._retry_count += 1
                if self._retry_count <= self._max_retries:
                    self._retry_unsub = event.async_track_point_in_utc_time(
                        self.hass,
                        self._handle_retry,
                        utcnow() + timedelta(seconds=RETRY_DELAY_SECONDS),
                    )
                    _LOGGER.warning(
                        "%s # Since updating failed and scan_interval = 0, retry %s of %s will be scheduled in %s seconds",
                        self._config_name,
                        self._retry_count,
                        self._max_retries,
                        RETRY_DELAY_SECONDS,
                    )
                elif self._max_retries == 0:
                    self._retry_count = 0
                    _LOGGER.debug(
                        "%s # Automatic retry is disabled (max_retries: 0)",
                        self._config_name,
                    )
                else:
                    # Re-arm the retries so a manual trigger gets a fresh set.
                    self._retry_count = 0
                    _LOGGER.error(
                        "%s # Updating and %s retries failed and scan_interval = 0, please manually retry with trigger service.",
                        self._config_name,
                        self._max_retries,
                    )

    async def _handle_retry(self, _now: datetime) -> None:
        """Run a scheduled retry of a failed update."""
        self._retry_unsub = None
        if self.hass.is_stopping:
            _LOGGER.debug(
                "%s # Home Assistant is stopping, skipping scheduled retry",
                self._config_name,
            )
            return
        # async_refresh() takes the debouncer lock instead of going through the
        # debouncer, so a retry can never be silently dropped.
        await self.async_refresh()

    @callback
    def _async_cancel_retry(self) -> None:
        """Cancel a pending retry, if any."""
        if self._retry_unsub:
            self._retry_unsub()
            self._retry_unsub = None

    async def async_shutdown(self) -> None:
        """Cancel any scheduled retry and shut down the coordinator."""
        self._async_cancel_retry()
        await super().async_shutdown()

    async def _prepare_new_run(self) -> None:
        _LOGGER.debug(
            "%s # New run: start (re)loading data from resource", self._config_name
        )
        self.update_error = False
        if self._file_manager:
            _LOGGER.debug(
                "%s # Deleting logging files from previous run", self._config_name
            )
            try:
                await self.hass.async_add_executor_job(self._file_manager.empty_folder)
            except Exception as ex:
                _LOGGER.error(
                    "%s # Error deleting files from previous run: %s",
                    self._config_name,
                    ex,
                )

        self._scraper.reset()

    @property
    def scrape_context(self) -> ScrapeContext:
        """Return the current scrape context with form variables."""
        return ScrapeContext(form_variables=self._request_manager.form_variables)
