"""Support for Multiscrape sensors."""
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import httpx
import voluptuous as vol
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_AUTHENTICATION
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
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
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_USERNAME
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.const import HTTP_DIGEST_AUTHENTICATION
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_PARSER
from .const import CONF_SELECTORS
from .const import DEFAULT_SCAN_INTERVAL
from .schema import PLATFORM_SCHEMA
from .scraped_rest_data import ScrapedRestData

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
)

_LOGGER = logging.getLogger(__name__)


def _create_rest_scraper_data_from_config(hass, config):
    resource = config.get(CONF_RESOURCE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    headers = config.get(CONF_HEADERS)
    params = config.get(CONF_PARAMS)
    timeout = config.get(CONF_TIMEOUT)

    selectors = config.get(CONF_SELECTORS)
    parser = config.get(CONF_PARSER)

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
        selectors,
        parser,
        timeout,
    )


def _create_rest_coordinator(hass, scraper, resource_template, update_interval):
    """Wrap a DataUpdateCoordinator around the rest object."""
    if resource_template:

        async def _async_refresh_with_resource_template():
            scraper.set_url(resource_template.async_render(parse_result=False))
            await scraper.async_update()

        update_method = _async_refresh_with_resource_template
    else:
        update_method = scraper.async_update

    return DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="multiscrape scraped rest data",
        update_method=update_method,
        update_interval=update_interval,
    )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Multiscrape sensor."""
    scan_interval = config.get(
        CONF_SCAN_INTERVAL, timedelta(seconds=DEFAULT_SCAN_INTERVAL)
    )
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)

    scraper = _create_rest_scraper_data_from_config(hass, config)
    coordinator = _create_rest_coordinator(
        hass, scraper, resource_template, scan_interval
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    entities = []

    selectors = config.get(CONF_SELECTORS)

    # TODO: This is actually a bug, force_update should be implemented on selector/sensor level
    force_update = config.get(CONF_FORCE_UPDATE)

    for device, device_config in selectors.items():
        name = device_config.get(CONF_NAME)
        unit = device_config.get(CONF_UNIT_OF_MEASUREMENT)
        device_class = device_config.get(CONF_DEVICE_CLASS)

        entities.append(
            MultiscrapeSensor(
                hass,
                scraper,
                coordinator,
                device,
                device_class,
                name,
                unit,
                force_update,
            )
        )

    async_add_entities(entities, True)


class MultiscrapeSensor(SensorEntity):
    """Implementation of the Multiscrape sensor."""

    def __init__(
        self,
        hass,
        scraper,
        coordinator,
        key,
        device_class,
        name,
        unit_of_measurement,
        force_update,
    ):
        """Initialize the sensor."""
        self._hass = hass
        self._scraper = scraper
        self._coordinator = coordinator
        self._key = key
        self._device_class = device_class
        self._name = name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._force_update = force_update

        self._attributes = {}

        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, key, hass=hass)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device_class."""
        return self._device_class

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def state(self):
        """Return the state of the device."""
        return self._scraper.values[self._key]

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity. Only used by the generic entity update service."""
        await self._coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes
