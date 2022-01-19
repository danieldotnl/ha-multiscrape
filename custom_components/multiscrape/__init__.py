"""The multiscrape component."""
import asyncio
import logging
import os
from datetime import timedelta

import voluptuous as vol
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_AUTHENTICATION
from homeassistant.const import CONF_DESCRIPTION
from homeassistant.const import CONF_HEADERS
from homeassistant.const import CONF_METHOD
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_PARAMS
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PAYLOAD
from homeassistant.const import CONF_RESOURCE
from homeassistant.const import CONF_RESOURCE_TEMPLATE
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.const import CONF_TIMEOUT
from homeassistant.const import CONF_USERNAME
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.helpers import discovery
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from .const import CONF_FIELDS
from .const import CONF_FORM_SUBMIT
from .const import CONF_LOG_RESPONSE
from .const import CONF_PARSER
from .const import COORDINATOR
from .const import DOMAIN
from .const import PLATFORM_IDX
from .const import SCRAPER
from .const import SCRAPER_DATA
from .const import SCRAPER_IDX
from .file import LoggingFileManager
from .http import HttpWrapper
from .schema import CONFIG_SCHEMA  # noqa: F401
from .scraper import Scraper

_LOGGER = logging.getLogger(__name__)
# we don't want to go with the default 15 seconds defined in helpers/entity_component
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

PLATFORMS = ["binary_sensor", "sensor", "button"]
COORDINATOR_AWARE_PLATFORMS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN, BUTTON_DOMAIN]


async def async_setup(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the multiscrape platforms."""
    _LOGGER.debug("# Start loading multiscrape")
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    _async_setup_shared_data(hass)

    async def reload_service_handler(service):
        """Remove all user-defined groups and load new ones from config."""
        conf = await component.async_prepare_reload()
        if conf is None:
            return
        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)
        _async_setup_shared_data(hass)
        await _async_process_config(hass, conf)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )
    _LOGGER.debug("# Reload service registered")

    return await _async_process_config(hass, entry)


def _async_setup_shared_data(hass: HomeAssistant):
    """Create shared data for platform config and scraper coordinators."""
    hass.data[DOMAIN] = {
        key: [] for key in [SCRAPER_DATA, *COORDINATOR_AWARE_PLATFORMS]
    }


async def _async_process_config(hass, config) -> bool:
    """Process scraper configuration."""

    _LOGGER.debug("# Start processing config from configuration.yaml")
    if DOMAIN not in config:
        _LOGGER.debug("# Multiscrape not found in config")
        return True

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

        scan_interval = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        resource_template = conf.get(CONF_RESOURCE_TEMPLATE)

        http = _create_http_wrapper(config_name, config, hass, file_manager)
        scraper = create_scraper_data_from_config(
            config_name, hass, http, conf, file_manager
        )
        coordinator = _create_scraper_coordinator(
            hass, config_name, scraper, resource_template, scan_interval
        )

        refresh_tasks.append(coordinator.async_refresh())
        hass.data[DOMAIN][SCRAPER_DATA].append(
            {SCRAPER: scraper, COORDINATOR: coordinator}
        )

        target_name = slugify(config_name)
        await _register_services(hass, target_name, coordinator)

        for platform_domain in COORDINATOR_AWARE_PLATFORMS:
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


async def _register_services(hass, target_name, coordinator):
    async def _async_trigger_service(service: ServiceCall):
        _LOGGER.info("Multiscrape triggered by service: %s", service.__repr__())
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        f"trigger_{target_name}",
        _async_trigger_service,
        schema=vol.Schema({}),
    )

    # Register the service description
    service_desc = {
        CONF_NAME: f"Trigger an update of {target_name}",
        CONF_DESCRIPTION: f"Triggers an update for the multiscrape {target_name} integration, independent of the update interval.",
        CONF_FIELDS: {},
    }
    async_set_service_schema(hass, DOMAIN, target_name, service_desc)


async def async_get_config_and_coordinator(hass, platform_domain, discovery_info):
    """Get the config and coordinator for the platform from discovery."""
    shared_data = hass.data[DOMAIN][SCRAPER_DATA][discovery_info[SCRAPER_IDX]]
    conf = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]
    coordinator = shared_data[COORDINATOR]
    scraper = shared_data[SCRAPER]
    if scraper.data is None:
        await coordinator.async_request_refresh()
    return conf, coordinator, scraper


def _create_http_wrapper(config_name, config, hass, file_manager):
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    auth_type = config.get(CONF_AUTHENTICATION)
    timeout = config.get(CONF_TIMEOUT)

    client = get_async_client(hass, verify_ssl)
    http = HttpWrapper(config_name, hass, client, file_manager, timeout)
    if username and password:
        http.set_authentication(username, password, auth_type)
    return http


def _create_scraper_coordinator(
    hass, name, scraper, resource_template, update_interval
):
    """Wrap a DataUpdateCoordinator around the scraper object."""

    if resource_template:
        _LOGGER.debug("%s # Setup coordinator", name)

        async def _async_refresh_with_resource_template():
            resource = resource_template.async_render(parse_result=False)
            _LOGGER.debug("%s # Rendered resource template into: %s", name, resource)
            scraper.set_url(resource)
            await scraper.async_update()

        update_method = _async_refresh_with_resource_template
    else:
        update_method = scraper.async_update

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="scraper data",
        update_method=update_method,
        update_interval=update_interval,
    )


def create_scraper_data_from_config(config_name, hass, http, config, file_manager):
    resource = config.get(CONF_RESOURCE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)
    method = config.get(CONF_METHOD).lower()
    payload = config.get(CONF_PAYLOAD)

    headers = config.get(CONF_HEADERS)
    params = config.get(CONF_PARAMS)
    parser = config.get(CONF_PARSER)
    form_submit = config.get(CONF_FORM_SUBMIT)

    if resource_template is not None:
        resource_template.hass = hass
        resource = resource_template.async_render(parse_result=False)
        _LOGGER.debug("%s # Rendered resource template into: %s", config_name, resource)

    return Scraper(
        hass,
        file_manager,
        http,
        config_name,
        method,
        resource,
        headers,
        params,
        payload,
        parser,
        form_submit,
    )
