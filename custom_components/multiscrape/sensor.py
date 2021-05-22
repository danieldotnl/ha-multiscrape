"""Support for Multiscrape sensors."""
import logging

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from bs4 import BeautifulSoup
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
from homeassistant.const import CONF_HEADERS
from homeassistant.const import CONF_METHOD
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PAYLOAD
from homeassistant.const import CONF_RESOURCE
from homeassistant.const import CONF_RESOURCE_TEMPLATE
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.const import CONF_TIMEOUT
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_USERNAME
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ATTR
from .const import CONF_INDEX
from .const import CONF_PARSER
from .const import CONF_SELECT
from .const import CONF_SELECTORS
from .schema import PLATFORM_SCHEMA

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Multiscrape sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    resource_template = config.get(CONF_RESOURCE_TEMPLATE)
    method = config.get(CONF_METHOD)
    payload = config.get(CONF_PAYLOAD)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    headers = config.get(CONF_HEADERS)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    selectors = config.get(CONF_SELECTORS)
    force_update = config.get(CONF_FORCE_UPDATE)
    timeout = config.get(CONF_TIMEOUT)
    parser = config.get(CONF_PARSER)
    scan_interval = config.get(CONF_SCAN_INTERVAL)

    session = async_get_clientsession(hass)

    auth = None
    if username and password:
        auth = aiohttp.BasicAuth(username, password)

    if resource_template is not None:
        resource_template.hass = hass
        resource = resource_template.async_render()

    def select_values(content):
        result = BeautifulSoup(content, parser)
        result.prettify()

        values = {}

        for device, device_config in selectors.items():
            key = device
            name = device_config.get(CONF_NAME)
            select = device_config.get(CONF_SELECT)
            attr = device_config.get(CONF_ATTR)
            index = device_config.get(CONF_INDEX)
            value_template = device_config.get(CONF_VALUE_TEMPLATE)

            if select is not None:
                select.hass = hass
                select = select.async_render()

            try:
                if attr is not None:
                    value = result.select(select)[index][attr]
                else:
                    tag = result.select(select)[index]
                    if tag.name in ("style", "script", "template"):
                        value = tag.string
                    else:
                        value = tag.text

                _LOGGER.debug("Sensor %s selected: %s", name, value)
            except IndexError as exception:
                _LOGGER.error("Sensor %s was unable to extract data from HTML", name)
                _LOGGER.debug("Exception: %s", exception)
                return

            if value_template is not None:
                value_template.hass = hass

                try:
                    values[key] = value_template.async_render_with_possible_json_value(
                        value, None
                    )
                except Exception as exception:
                    _LOGGER.error(exception)

            else:
                values[key] = value

        return values

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(timeout):
                async with session.request(
                    method,
                    resource,
                    auth=auth,
                    data=payload,
                    headers=headers,
                    ssl=verify_ssl,
                ) as response:
                    result = await response.text()
                    _LOGGER.debug("Response from %s: \n %s", resource, response)
                    return select_values(result)
        except Exception:
            raise UpdateFailed

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="multiscrape",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=scan_interval,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    entities = []

    for device, device_config in selectors.items():
        name = device_config.get(CONF_NAME)
        unit = device_config.get(CONF_UNIT_OF_MEASUREMENT)
        device_class = device_config.get(CONF_DEVICE_CLASS)

        entities.append(
            MultiscrapeSensor(
                hass,
                coordinator,
                device,
                device_class,
                name,
                unit,
                force_update,
            )
        )

    async_add_entities(entities, True)


class UpdateFailed(Exception):
    """Raised when an update has failed."""


class MultiscrapeSensor(SensorEntity):
    """Implementation of the Multiscrape sensor."""

    def __init__(
        self,
        hass,
        coordinator,
        key,
        device_class,
        name,
        unit_of_measurement,
        force_update,
    ):
        """Initialize the sensor."""
        self._hass = hass
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
        return self._coordinator.data[self._key]

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
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes
