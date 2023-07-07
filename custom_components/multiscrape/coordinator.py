import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import event
from homeassistant.util.dt import utcnow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MultiscrapeDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        config_name,
        hass: HomeAssistant,
        http,
        file_manager,
        form_submitter,
        scraper,
        update_interval: timedelta | None,
        resource_renderer,
        method,
        data_renderer,
    ):
        self._hass = hass
        self._config_name = config_name
        self._http = http
        self._file_manager = file_manager
        self._scraper = scraper
        self._form_submitter = form_submitter
        self._resource_renderer = resource_renderer
        self._method = method
        self._update_interval = update_interval
        self._data_renderer = data_renderer
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
        if self._form_submitter:
            self._form_submitter.notify_scrape_exception()

    async def _async_update_data(self):
        _LOGGER.debug(
            "%s # New run: start (re)loading data from resource", self._config_name
        )
        await self._prepare_new_run()

        if self._form_submitter and self._form_submitter.should_submit:
            try:
                result = await self._form_submitter.async_submit(self._resource)

                if result:
                    _LOGGER.debug(
                        "%s # Using response from form-submit as data. Now ready to be scraped by sensors.",
                        self._config_name,
                    )
                    await self._scraper.set_content(result)
                    return
            except Exception as ex:
                _LOGGER.error(
                    "%s # Exception in form-submit feature. Will continue trying to scrape target page.\n%s",
                    self._config_name,
                    ex,
                )

        _LOGGER.debug("%s # Request data from %s", self._config_name, self._resource)
        try:
            response = await self._http.async_request(
                "page", self._method, self._resource, self._data_renderer(None)
            )
            await self._scraper.set_content(response.text)
            _LOGGER.debug(
                "%s # Data succesfully refreshed. Sensors will now start scraping to update.",
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
                    _LOGGER.warning(
                        "%s # Updating and 3 retries failed and scan_interval = 0, please manually retry with trigger service.",
                        self._config_name,
                    )

    async def _prepare_new_run(self):
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

        self._resource = self._resource_renderer(None)
        _LOGGER.debug(
            "%s # Rendered resource template into: %s",
            self._config_name,
            self._resource,
        )

        self._scraper.reset()

    async def _async_file_log(self, content_name, content):
        try:
            filename = f"{content_name}.txt"
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
