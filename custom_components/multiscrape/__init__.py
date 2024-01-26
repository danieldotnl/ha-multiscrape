"""The multiscrape component."""
import asyncio
import contextlib
import logging
import os

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME

from homeassistant.const import Platform
from homeassistant.const import SERVICE_RELOAD, CONF_RESOURCE, CONF_RESOURCE_TEMPLATE
from homeassistant.core import HomeAssistant

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.util import slugify

from .service import setup_config_services, setup_integration_services

from .const import CONF_FORM_SUBMIT
from .const import CONF_LOG_RESPONSE
from .const import CONF_PARSER
from .const import COORDINATOR
from .const import DOMAIN
from .const import PLATFORM_IDX
from .const import SCRAPER
from .const import SCRAPER_DATA
from .const import SCRAPER_IDX
from .coordinator import (
    create_multiscrape_coordinator,
)
from .coordinator import create_content_request_manager
from .file import LoggingFileManager
from .form import create_form_submitter
from .http import create_http_wrapper
from .schema import COMBINED_SCHEMA, CONFIG_SCHEMA  # noqa: F401
from .scraper import create_scraper

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the multiscrape platforms."""
    _LOGGER.debug("# Start loading multiscrape")
    _async_setup_shared_data(hass)

    async def reload_service_handler(service):
        """Remove all user-defined groups and load new ones from config."""
        conf = None
        with contextlib.suppress(HomeAssistantError):
            conf = await async_integration_yaml_config(hass, DOMAIN)
        if conf is None:
            return
        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)
        _async_setup_shared_data(hass)
        await _async_process_config(hass, conf)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )
    _LOGGER.debug("# Reload service registered")

    await setup_integration_services(hass)

    if len(entry[DOMAIN]) == 1:
        if not entry[DOMAIN][0].get(CONF_RESOURCE) and not entry[DOMAIN][0].get(
            CONF_RESOURCE_TEMPLATE
        ):
            _LOGGER.info(
                "Did not find any configuration. Assuming we want just the integration level services."
            )
            return True

    return await _async_process_config(hass, entry)


def _async_setup_shared_data(hass: HomeAssistant):
    """Create shared data for platform config and scraper coordinators."""
    hass.data[DOMAIN] = {key: [] for key in [SCRAPER_DATA, *PLATFORMS]}


async def _async_process_config(hass: HomeAssistant, config) -> bool:
    """Process scraper configuration."""

    _LOGGER.debug("# Start processing config from configuration.yaml")

    refresh_tasks = []
    load_tasks = []

    for scraper_idx, conf in enumerate(config[DOMAIN]):
        config_name = conf.get(CONF_NAME)
        if config_name is None:
            config_name = f"Scraper_noname_{scraper_idx}"
            _LOGGER.debug(
                "# Found no name for scraper, generated a unique name: %s", config_name
            )

        _LOGGER.debug(
            "%s # Setting up multiscrape with config:\n %s", config_name, conf
        )

        file_manager = None
        log_response = conf.get(CONF_LOG_RESPONSE)
        if log_response:
            folder = os.path.join(
                hass.config.config_dir, f"multiscrape/{slugify(config_name)}/"
            )
            _LOGGER.debug(
                "%s # Log responses enabled, creating logging folder: %s",
                config_name,
                folder,
            )
            file_manager = LoggingFileManager(folder)
            await hass.async_add_executor_job(file_manager.create_folders)

        http = create_http_wrapper(config_name, conf, hass, file_manager)

        form_submit_config = conf.get(CONF_FORM_SUBMIT)
        form_submitter = None
        if form_submit_config:
            parser = conf.get(CONF_PARSER)
            form_submitter = create_form_submitter(
                config_name, form_submit_config, hass, http, file_manager, parser
            )

        scraper = create_scraper(config_name, conf, hass, file_manager)

        request_manager = create_content_request_manager(
            config_name, conf, hass, http, form_submitter
        )
        coordinator = create_multiscrape_coordinator(
            config_name,
            conf,
            hass,
            request_manager,
            file_manager,
            scraper,
        )

        refresh_tasks.append(coordinator.async_refresh())
        hass.data[DOMAIN][SCRAPER_DATA].append(
            {SCRAPER: scraper, COORDINATOR: coordinator}
        )

        for platform_domain in PLATFORMS:
            if platform_domain not in conf:
                continue

            for platform_conf in conf[platform_domain]:
                hass.data[DOMAIN][platform_domain].append(platform_conf)
                platform_idx = len(hass.data[DOMAIN][platform_domain]) - 1

                load = discovery.async_load_platform(
                    hass,
                    platform_domain,
                    DOMAIN,
                    {SCRAPER_IDX: scraper_idx, PLATFORM_IDX: platform_idx},
                    config,
                )
                load_tasks.append(load)

    if refresh_tasks:
        await asyncio.gather(*refresh_tasks)

    if load_tasks:
        await asyncio.gather(*load_tasks)

    await setup_config_services(hass, coordinator, config_name)
    return True


async def async_get_config_and_coordinator(hass, platform_domain, discovery_info):
    """Get the config and coordinator for the platform from discovery."""
    shared_data = hass.data[DOMAIN][SCRAPER_DATA][discovery_info[SCRAPER_IDX]]
    conf = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]
    coordinator = shared_data[COORDINATOR]
    scraper = shared_data[SCRAPER]
    return conf, coordinator, scraper
