"""The multiscrape component."""
import asyncio
import logging
from datetime import timedelta

import httpx
import voluptuous as vol
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
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
from homeassistant.const import HTTP_DIGEST_AUTHENTICATION
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.helpers import discovery
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from .const import CONF_FIELDS
from .const import CONF_FORM_SUBMIT
from .const import CONF_PARSER
from .const import COORDINATOR
from .const import DOMAIN
from .const import PLATFORM_IDX
from .const import REST
from .const import REST_DATA
from .const import REST_IDX
from .data import ScrapedRestData
from .schema import CONFIG_SCHEMA  # noqa: F401

_LOGGER = logging.getLogger(__name__)
# we don't want to go with the default 15 seconds defined in helpers/entity_component
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

PLATFORMS = ["binary_sensor", "sensor"]
COORDINATOR_AWARE_PLATFORMS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the multiscrape platforms."""
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

    return await _async_process_config(hass, config)


@callback
def _async_setup_shared_data(hass: HomeAssistant):
    """Create shared data for platform config and rest coordinators."""
    hass.data[DOMAIN] = {key: [] for key in [REST_DATA, *COORDINATOR_AWARE_PLATFORMS]}


async def _async_process_config(hass, config) -> bool:
    """Process rest configuration."""
    if DOMAIN not in config:
        return True

    refresh_tasks = []
    load_tasks = []
    for rest_idx, conf in enumerate(config[DOMAIN]):
        name = conf.get(CONF_NAME)
        scan_interval = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        resource_template = conf.get(CONF_RESOURCE_TEMPLATE)
        rest = create_rest_data_from_config(hass, conf)
        coordinator = _rest_coordinator(hass, rest, resource_template, scan_interval)
        refresh_tasks.append(coordinator.async_refresh())
        hass.data[DOMAIN][REST_DATA].append({REST: rest, COORDINATOR: coordinator})

        if name:
            target_name = slugify(name)
        else:
            target_name = f"noname_{rest_idx}"

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
                    {REST_IDX: rest_idx, PLATFORM_IDX: platform_idx},
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
    shared_data = hass.data[DOMAIN][REST_DATA][discovery_info[REST_IDX]]
    conf = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]
    coordinator = shared_data[COORDINATOR]
    rest = shared_data[REST]
    if rest.data is None:
        await coordinator.async_request_refresh()
    return conf, coordinator, rest


def _rest_coordinator(hass, rest, resource_template, update_interval):
    """Wrap a DataUpdateCoordinator around the rest object."""
    if resource_template:

        async def _async_refresh_with_resource_template():
            rest.set_url(resource_template.async_render(parse_result=False))
            await rest.async_update()

        update_method = _async_refresh_with_resource_template
    else:
        update_method = rest.async_update

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="rest data",
        update_method=update_method,
        update_interval=update_interval,
    )


def create_rest_data_from_config(hass, config):
    """Create RestData from config."""
    resource = config.get(CONF_RESOURCE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    headers = config.get(CONF_HEADERS)
    params = config.get(CONF_PARAMS)
    parser = config.get(CONF_PARSER)
    timeout = config.get(CONF_TIMEOUT)
    form_submit = config.get(CONF_FORM_SUBMIT)

    if resource_template is not None:
        resource_template.hass = hass
        resource = resource_template.async_render(parse_result=False)

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = httpx.DigestAuth(username, password)
        else:
            auth = (username, password)
    else:
        auth = None

    return ScrapedRestData(
        hass,
        method,
        resource,
        auth,
        headers,
        params,
        payload,
        verify_ssl,
        parser,
        form_submit,
        timeout,
    )
