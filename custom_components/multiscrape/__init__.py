"""The multiscrape component."""
import asyncio
import contextlib
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_NAME, CONF_RESOURCE,
                                 CONF_RESOURCE_TEMPLATE, SERVICE_RELOAD,
                                 Platform)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.helpers.reload import (async_integration_yaml_config,
                                          async_reload_integration_platforms)

from .const import (CONF_FORM_SUBMIT, CONF_LOG_RESPONSE, CONF_PARSER,
                    COORDINATOR, DOMAIN, PLATFORM_IDX, SCRAPER, SCRAPER_DATA,
                    SCRAPER_IDX)
from .coordinator import (create_content_request_manager,
                          create_multiscrape_coordinator)
from .file import create_file_manager
from .form import create_form_submitter
from .http import create_http_wrapper
from .schema import COMBINED_SCHEMA, CONFIG_SCHEMA  # noqa: F401
from .scraper import create_scraper
from .service import setup_config_services, setup_integration_services

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

        file_manager = await create_file_manager(hass, config_name, conf.get(CONF_LOG_RESPONSE))
        form_submit_config = conf.get(CONF_FORM_SUBMIT)
        form_submitter = None
        if form_submit_config:
            parser = conf.get(CONF_PARSER)
            form_http = create_http_wrapper(config_name, form_submit_config, hass, file_manager)
            form_submitter = create_form_submitter(
                config_name,
                form_submit_config,
                hass,
                form_http,
                file_manager,
                parser,
            )

        http = create_http_wrapper(config_name, conf, hass, file_manager)
        scraper = create_scraper(config_name, conf, hass, file_manager)
        request_manager = create_content_request_manager(config_name, conf, hass, http, form_submitter)
        coordinator = create_multiscrape_coordinator(
            config_name,
            conf,
            hass,
            request_manager,
            file_manager,
            scraper,
        )
        await coordinator.async_register_shutdown()

        hass.data[DOMAIN][SCRAPER_DATA].append(
            {SCRAPER: scraper, COORDINATOR: coordinator}
        )

        await setup_config_services(hass, coordinator, config_name)

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


    return True


async def async_get_config_and_coordinator(hass, platform_domain, discovery_info):
    """Get the config and coordinator for the platform from discovery."""
    shared_data = hass.data[DOMAIN][SCRAPER_DATA][discovery_info[SCRAPER_IDX]]
    conf = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]
    coordinator = shared_data[COORDINATOR]
    scraper = shared_data[SCRAPER]
    return conf, coordinator, scraper
