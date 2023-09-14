"""Coordinator class for multiscrape integration."""
import logging
from datetime import timedelta
from collections.abc import Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import event
from homeassistant.util.dt import utcnow

from .scraper import Scraper
from .http import HttpWrapper
from .file import LoggingFileManager
from .form import FormSubmitter

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ContentRequestManager:
    """Responsible for orchestrating all request required to retrieve the desired content."""

    def __init__(
        self,
        config_name: str,
        http: HttpWrapper,
        resource_renderer: Callable,
        form: FormSubmitter = None,
    ) -> None:
        """Initialize RequestManagerMixin."""
        self._config_name = config_name
        self._http = http
        self._form_submitter = form
        self._resource_renderer = resource_renderer

    def notify_scrape_exception(self):
        """Notify the form_submitter of an exception so it will re-submit next trigger."""
        if self._form_submitter:
            self._form_submitter.notify_scrape_exception()

    async def get_content(self) -> str:
        """Retrieve the content of a url and first submit a form if required."""
        resource = self._resource_renderer()

        if self._form_submitter:
            try:
                result = await self._form_submitter.async_submit(resource)

                if result:
                    _LOGGER.debug(
                        "%s # Using response from form-submit as content for scraping.",
                        self._config_name,
                    )
                    return result
            except Exception as ex:
                _LOGGER.error(
                    "%s # Exception in form-submit feature. Will continue trying to scrape target page.\n%s",
                    self._config_name,
                    ex,
                )

        response = await self._http.async_request("page", resource)
        return response.text


class MultiscrapeDataUpdateCoordinator(DataUpdateCoordinator):
    """Multiscrape coordinator class."""

    def __init__(
        self,
        config_name,
        hass: HomeAssistant,
        request_manager: ContentRequestManager,
        file_manager: LoggingFileManager,
        scraper: Scraper,
        update_interval: timedelta | None,
    ):
        """Initialize the coordinator."""
        self._hass = hass
        self._config_name = config_name
        self._request_manager = request_manager
        self._file_manager = file_manager
        self._scraper = scraper
        self._update_interval = update_interval
        self.update_error = False
        self._resource = None
        self._retry: int = 0

        if self._update_interval == timedelta(seconds=0):
            self._update_interval = None

        _LOGGER.debug(
            "%s # Scan interval is %s", self._config_name, self._update_interval
        )

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=self._update_interval
        )

    def notify_scrape_exception(self):
        """Notify the ContentRequestManager of a scrape exception so it can notify the FormSubmitter."""
        self._request_manager.notify_scrape_exception()

    async def _async_update_data(self):
        await self._prepare_new_run()

        try:
            response = await self._request_manager.get_content()
            await self._scraper.set_content(response)
            _LOGGER.debug(
                "%s # Data successfully refreshed. Sensors will now start scraping to update.",
                self._config_name,
            )
            self._retry = 0

        except Exception as ex:
            _LOGGER.error(
                "%s # Updating failed with exception: %s",
                self._config_name,
                ex,
            )
            self._scraper.reset()
            self.update_error = True
            if self._update_interval is None:
                self._async_unsub_refresh()
                if self._retry < 3:
                    self._unsub_refresh = event.async_track_point_in_utc_time(
                        self.hass,
                        self._job,
                        utcnow().replace(microsecond=self._microsecond)
                        + timedelta(seconds=30),
                    )
                    _LOGGER.warning(
                        "%s # Since updating failed and scan_interval = 0, retry %s of 3 will be scheduled in 30 seconds",
                        self._config_name,
                        self._retry + 1,
                    )
                    self._retry = self._retry + 1
                else:
                    _LOGGER.error(
                        "%s # Updating and 3 retries failed and scan_interval = 0, please manually retry with trigger service.",
                        self._config_name,
                    )

    async def _prepare_new_run(self):
        _LOGGER.debug(
            "%s # New run: start (re)loading data from resource", self._config_name
        )
        self.update_error = False
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

        self._scraper.reset()
