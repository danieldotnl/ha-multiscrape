import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


class MultiscrapeDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        config_name,
        hass,
        http,
        file_manager,
        form_submitter,
        scraper,
        update_interval,
        resource,
        resource_template,
        method,
    ):
        self._hass = hass
        self._config_name = config_name
        self._http = http
        self._file_manager = file_manager
        self._scraper = scraper
        self._form_submitter = form_submitter
        self._resource = resource
        self._resource_template = resource_template
        self._method = method

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

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
                "page",
                self._method,
                self._resource,
            )
            await self._scraper.set_content(response.text)
            _LOGGER.debug(
                "%s # Data succesfully refreshed. Sensors will now start scraping to update.",
                self._config_name,
            )
        except Exception as ex:
            _LOGGER.error(
                "%s # Updating failed with exception: %s",
                self._config_name,
                ex,
            )
            self._scraper.reset()
            raise UpdateFailed("Unable to update data from resource")

    async def _prepare_new_run(self):
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

        if self._resource_template:
            self._resource = self._resource_template.async_render(parse_result=False)
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
