"""Class for implementing the multiscrape services."""

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall, SupportsResponse
from homeassistant.const import (
    CONF_NAME,
    CONF_DESCRIPTION,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    CONF_ICON,
)
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.util import slugify
from homeassistant.const import Platform

from .scraper import create_scraper

from .form import create_form_submitter

from .selector import Selector
from .schema import SERVICE_COMBINED_SCHEMA
from .coordinator import (
    MultiscrapeDataUpdateCoordinator,
    create_content_request_manager,
)
from .http import create_http_wrapper

from .const import (
    CONF_FORM_SUBMIT,
    CONF_PARSER,
    CONF_SENSOR_ATTRS,
    DOMAIN,
    CONF_FIELDS,
)

_LOGGER = logging.getLogger(__name__)


async def setup_integration_services(hass: HomeAssistant):
    """Set up the multiscrape integration level services."""
    _LOGGER.debug("Setting up multiscrape integration level services")
    await setup_get_content_service(hass)
    await setup_scrape_service(hass)


async def setup_config_services(
    hass: HomeAssistant, coordinator: MultiscrapeDataUpdateCoordinator, config_name: str
):
    """Set up the multiscrape configuration level services."""
    _LOGGER.debug(
        "%s # Setting up multiscrape configuration level services", config_name
    )
    target_name = slugify(config_name)
    await _setup_trigger_service(hass, target_name, coordinator)


async def _setup_trigger_service(hass: HomeAssistant, target_name, coordinator):
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
    async_set_service_schema(hass, DOMAIN, f"trigger_{target_name}", service_desc)


async def setup_get_content_service(hass: HomeAssistant):
    """Set up the multiscrape get_content service."""

    async def _async_get_content_service(service: ServiceCall) -> None:
        _LOGGER.info("Get_content service triggered: %s", service.__repr__())
        config_name = "get_content_service"
        conf = _restore_templates(service.data)
        request_manager, scraper = await _prepare_service_request(
            hass, conf, config_name
        )
        result = await request_manager.get_content()
        await scraper.set_content(result)
        return {"content": str(scraper.formatted_content)}

    hass.services.async_register(
        DOMAIN,
        "get_content",
        _async_get_content_service,
        schema=SERVICE_COMBINED_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def setup_scrape_service(hass: HomeAssistant):
    """Set up the multiscrape scrape service."""

    async def _async_scrape_service(service: ServiceCall) -> None:
        _LOGGER.info("Scrape service triggered: %s", service.__repr__())
        conf = _restore_templates(service.data)
        config_name = "scrape_service"
        request_manager, scraper = await _prepare_service_request(
            hass, conf, config_name
        )
        result = await request_manager.get_content()
        await scraper.set_content(result)

        response = {}

        for platform in [Platform.SENSOR, Platform.BINARY_SENSOR]:
            for sensor in conf.get(platform) or []:
                name = sensor.get(CONF_UNIQUE_ID) or slugify(sensor.get(CONF_NAME))
                sensor_selector = Selector(hass, sensor)
                response[name] = {"value": scraper.scrape(sensor_selector, config_name)}

                if sensor.get(CONF_ICON):
                    response[CONF_ICON] = sensor.get(CONF_ICON).async_render(
                        variables={"value": response[name]}, parse_result=False
                    )

                for attr_conf in sensor.get(CONF_SENSOR_ATTRS) or []:
                    attr_name = slugify(attr_conf[CONF_NAME])
                    attr_selector = Selector(hass, attr_conf)
                    response[name].setdefault(CONF_SENSOR_ATTRS, {}).update(
                        {attr_name: scraper.scrape(attr_selector, config_name)}
                    )

        return response

    hass.services.async_register(
        DOMAIN,
        "scrape",
        _async_scrape_service,
        schema=SERVICE_COMBINED_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def _prepare_service_request(hass: HomeAssistant, conf, config_name):
    http = create_http_wrapper(config_name, conf, hass, None)
    form_submitter = None
    form_submit_config = conf.get(CONF_FORM_SUBMIT)
    parser = conf.get(CONF_PARSER)
    if form_submit_config:
        form_submitter = create_form_submitter(
            config_name, form_submit_config, hass, http, None, parser
        )
    request_manager = create_content_request_manager(
        config_name, conf, hass, http, form_submitter
    )
    scraper = create_scraper(config_name, conf, hass, None)
    return request_manager, scraper


def _restore_templates(config):
    config = dict(config)
    for platform in [Platform.SENSOR, Platform.BINARY_SENSOR]:
        for sensor in config.get(platform) or []:
            for attr_conf in sensor.get(CONF_SENSOR_ATTRS) or []:
                attr_conf[CONF_VALUE_TEMPLATE] = (
                    cv.template(
                        _replace_template_characters(attr_conf.get(CONF_VALUE_TEMPLATE))
                    )
                    if attr_conf.get(CONF_VALUE_TEMPLATE)
                    else None
                )
            if sensor.get(CONF_ICON):
                sensor[CONF_ICON] = cv.template(
                    _replace_template_characters(sensor.get(CONF_ICON))
                )
            if sensor.get(CONF_VALUE_TEMPLATE):
                sensor[CONF_VALUE_TEMPLATE] = cv.template(
                    _replace_template_characters(sensor.get(CONF_VALUE_TEMPLATE))
                )
    return config


def _replace_template_characters(template: str):
    template = template.replace("{!{", "{{").replace("}!}", "}}")
    template = template.replace("{!%", "{%").replace("%!}", "%}")
    return template
