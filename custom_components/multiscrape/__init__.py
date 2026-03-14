"""The multiscrape component."""
import asyncio
import contextlib
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_NAME, CONF_RESOURCE,
                                 CONF_RESOURCE_TEMPLATE,
                                 EVENT_HOMEASSISTANT_STOP, SERVICE_RELOAD,
                                 Platform)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.helpers.reload import (async_integration_yaml_config,
                                          async_reload_integration_platforms)
from homeassistant.util import slugify

from .const import CONF_LOG_RESPONSE, DOMAIN, ENTITY_KEY, SCRAPER_ID
from .coordinator import (create_content_request_manager,
                          create_multiscrape_coordinator)
from .file import create_file_manager
from .http_session import create_http_session
from .registry import ScraperInstance, ScraperRegistry
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
    """Create a fresh ScraperRegistry for platform config and scraper coordinators."""
    hass.data[DOMAIN] = ScraperRegistry()


async def _async_process_config(hass: HomeAssistant, config) -> bool:
    """Process scraper configuration."""

    _LOGGER.debug("# Start processing config from configuration.yaml")

    refresh_tasks = []
    load_tasks = []
    registry: ScraperRegistry = hass.data[DOMAIN]

    for scraper_idx, conf in enumerate(config[DOMAIN]):
        config_name = conf.get(CONF_NAME)
        if config_name is None:
            resource = conf.get(CONF_RESOURCE) or ""
            config_name = (
                f"scraper_{slugify(resource)}" if resource else f"scraper_unnamed_{scraper_idx}"
            )
            _LOGGER.debug(
                "# Found no name for scraper, generated name: %s", config_name
            )

        _LOGGER.debug(
            "%s # Setting up multiscrape with config:\n %s", config_name, conf
        )

        scraper_id = _deduplicate_id(registry, config_name)

        file_manager = await create_file_manager(hass, config_name, conf.get(CONF_LOG_RESPONSE))
        session = create_http_session(config_name, conf, hass, file_manager)
        scraper = create_scraper(config_name, conf, hass, file_manager)
        request_manager = create_content_request_manager(config_name, conf, hass, session)
        coordinator = create_multiscrape_coordinator(
            config_name,
            conf,
            hass,
            request_manager,
            file_manager,
            scraper,
        )
        await coordinator.async_register_shutdown()

        async def _shutdown_session(_event, _session=session):
            await _session.async_close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_session)

        instance = ScraperInstance(
            scraper_id=scraper_id,
            scraper=scraper,
            coordinator=coordinator,
        )
        registry.register(instance)

        await setup_config_services(hass, coordinator, config_name)

        for platform_domain in PLATFORMS:
            if platform_domain not in conf:
                continue

            for platform_conf in conf[platform_domain]:
                entity_name = platform_conf.get(CONF_NAME, "")
                entity_key = slugify(entity_name) if entity_name else f"entity_{id(platform_conf)}"

                platform_dict = instance.platform_configs.setdefault(platform_domain, {})
                entity_key = _deduplicate_entity_key(platform_dict, entity_key)
                platform_dict[entity_key] = platform_conf

                load = discovery.async_load_platform(
                    hass,
                    platform_domain,
                    DOMAIN,
                    {SCRAPER_ID: scraper_id, ENTITY_KEY: entity_key},
                    config,
                )
                load_tasks.append(load)

    if refresh_tasks:
        await asyncio.gather(*refresh_tasks)

    if load_tasks:
        await asyncio.gather(*load_tasks)


    return True


def _deduplicate_id(registry: ScraperRegistry, base_id: str) -> str:
    """Return a unique scraper ID, appending a suffix if needed."""
    if not registry.contains(base_id):
        return base_id
    suffix = 2
    while registry.contains(f"{base_id}_{suffix}"):
        suffix += 1
    deduped = f"{base_id}_{suffix}"
    _LOGGER.warning(
        "Duplicate scraper name '%s', using '%s' instead", base_id, deduped
    )
    return deduped


def _deduplicate_entity_key(platform_dict: dict, base_key: str) -> str:
    """Return a unique entity key within a platform, appending a suffix if needed."""
    if base_key not in platform_dict:
        return base_key
    suffix = 2
    while f"{base_key}_{suffix}" in platform_dict:
        suffix += 1
    deduped = f"{base_key}_{suffix}"
    _LOGGER.warning(
        "Duplicate entity name '%s', using '%s' instead", base_key, deduped
    )
    return deduped


async def async_get_config_and_coordinator(hass, platform_domain, discovery_info):
    """Get the config and coordinator for the platform from discovery."""
    registry: ScraperRegistry = hass.data[DOMAIN]
    instance = registry.get(discovery_info[SCRAPER_ID])
    conf = instance.platform_configs[platform_domain][discovery_info[ENTITY_KEY]]
    return conf, instance.coordinator, instance.scraper
