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
from homeassistant.util import slugify

from .const import CONF_FIELDS
from .const import CONF_FORM_INPUT
from .const import CONF_FORM_RESOURCE
from .const import CONF_FORM_RESUBMIT_ERROR
from .const import CONF_FORM_SELECT
from .const import CONF_FORM_SUBMIT
from .const import CONF_FORM_SUBMIT_ONCE
from .const import CONF_LOG_RESPONSE
from .const import CONF_PARSER
from .const import COORDINATOR
from .const import DOMAIN
from .const import PLATFORM_IDX
from .const import SCRAPER
from .const import SCRAPER_DATA
from .const import SCRAPER_IDX
from .coordinator import MultiscrapeDataUpdateCoordinator
from .file import LoggingFileManager
from .form import FormSubmitter
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

        form_submit_config = conf.get(CONF_FORM_SUBMIT)
        form_submitter = None
        if form_submit_config:
            form_submit_http = _create_form_submit_http_wrapper(
                config_name, conf, hass, file_manager
            )
            parser = conf.get(CONF_PARSER)
            form_submitter = _create_form_submitter(
                config_name,
                form_submit_config,
                hass,
                form_submit_http,
                file_manager,
                parser,
            )

        scraper = _create_scraper(config_name, conf, hass, file_manager)
        http = _create_scrape_http_wrapper(config_name, conf, hass, file_manager)
        coordinator = _create_multiscrape_coordinator(
            config_name, conf, hass, http, file_manager, form_submitter, scraper
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
    if not scraper.has_data:
        await coordinator.async_request_refresh()
    return conf, coordinator, scraper


def _create_scrape_http_wrapper(config_name, config, hass, file_manager):
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    auth_type = config.get(CONF_AUTHENTICATION)
    timeout = config.get(CONF_TIMEOUT)
    data = config.get(CONF_PAYLOAD)
    headers = config.get(CONF_HEADERS)
    params = config.get(CONF_PARAMS)

    client = get_async_client(hass, verify_ssl)
    http = HttpWrapper(
        config_name,
        hass,
        client,
        file_manager,
        timeout,
        data=data,
        params=params,
        request_headers=headers,
    )
    if username and password:
        http.set_authentication(username, password, auth_type)
    return http


def _create_form_submit_http_wrapper(config_name, config, hass, file_manager):
    verify_ssl = config.get(CONF_VERIFY_SSL)
    timeout = config.get(CONF_TIMEOUT)
    headers = config.get(CONF_HEADERS)
    params = config.get(CONF_PARAMS)

    client = get_async_client(hass, verify_ssl)
    http = HttpWrapper(
        config_name,
        hass,
        client,
        file_manager,
        timeout,
        params=params,
        request_headers=headers,
    )
    return http


def _create_form_submitter(config_name, config, hass, http, file_manager, parser):
    resource = config.get(CONF_FORM_RESOURCE)
    select = config.get(CONF_FORM_SELECT)
    input_values = config.get(CONF_FORM_INPUT)
    resubmit_error = config.get(CONF_FORM_RESUBMIT_ERROR)
    submit_once = config.get(CONF_FORM_SUBMIT_ONCE)

    return FormSubmitter(
        config_name,
        hass,
        http,
        file_manager,
        resource,
        select,
        input_values,
        submit_once,
        resubmit_error,
        parser,
    )


def _create_multiscrape_coordinator(
    config_name, conf, hass, http, file_manager, form_submitter, scraper
):
    _LOGGER.debug("%s # Initializing coordinator", config_name)

    method = conf.get(CONF_METHOD).lower()
    scan_interval = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    resource = conf.get(CONF_RESOURCE)
    resource_template = conf.get(CONF_RESOURCE_TEMPLATE)

    if resource_template is not None:
        resource_template.hass = hass

    return MultiscrapeDataUpdateCoordinator(
        config_name,
        hass,
        http,
        file_manager,
        form_submitter,
        scraper,
        scan_interval,
        resource,
        resource_template,
        method,
    )


def _create_scraper(config_name, config, hass, file_manager):
    _LOGGER.debug("%s # Initializing scraper", config_name)
    parser = config.get(CONF_PARSER)

    return Scraper(
        config_name,
        hass,
        file_manager,
        parser,
    )
