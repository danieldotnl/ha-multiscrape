"""Support for Multiscrape sensors."""
import logging

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_RESOURCE_TEMPLATE
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.exceptions import PlatformNotReady

from . import async_get_config_and_coordinator
from .const import CONF_ATTR
from .const import CONF_INDEX
from .const import CONF_SELECT
from .const import CONF_SENSOR_ATTRS
from .entity import MultiscrapeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the multiscrape sensor."""
    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, rest = await async_get_config_and_coordinator(
            hass, SENSOR_DOMAIN, discovery_info
        )
    else:
        _LOGGER.error("Could not find sensor configuration")

    if rest.data is None:
        if rest.last_exception:
            raise PlatformNotReady from rest.last_exception
        raise PlatformNotReady

    name = conf.get(CONF_NAME)
    unit = conf.get(CONF_UNIT_OF_MEASUREMENT)
    device_class = conf.get(CONF_DEVICE_CLASS)
    select = conf.get(CONF_SELECT)
    attribute = conf.get(CONF_ATTR)
    index = conf.get(CONF_INDEX)
    value_template = conf.get(CONF_VALUE_TEMPLATE)
    force_update = conf.get(CONF_FORCE_UPDATE)
    resource_template = conf.get(CONF_RESOURCE_TEMPLATE)
    sensor_attributes = conf.get(CONF_SENSOR_ATTRS)

    if value_template is not None:
        value_template.hass = hass

    async_add_entities(
        [
            RestSensor(
                hass,
                coordinator,
                rest,
                name,
                unit,
                device_class,
                value_template,
                force_update,
                resource_template,
                select,
                attribute,
                index,
                sensor_attributes,
            )
        ],
    )


class RestSensor(MultiscrapeEntity, SensorEntity):
    """Implementation of a multiscrape sensor."""

    def __init__(
        self,
        hass,
        coordinator,
        rest,
        name,
        unit_of_measurement,
        device_class,
        value_template,
        force_update,
        resource_template,
        select_template,
        attribute,
        index,
        sensor_attributes,
    ):
        """Initialize the multiscrape sensor."""
        super().__init__(
            coordinator, rest, name, device_class, resource_template, force_update
        )
        self._state = None
        self._hass = hass
        self._unit_of_measurement = unit_of_measurement
        self._value_template = value_template
        self._attributes = None
        self._select_template = select_template
        self._attribute = attribute
        self._index = index
        self._sensor_attributes = sensor_attributes

        if self._select_template is not None:
            self._select_template.hass = self._hass
            self._select = self._select_template.async_render()
            _LOGGER.debug("Parsed select template: %s", self._select)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _update_from_rest_data(self):
        """Update state from the rest data."""

        value = self._scrape(
            self.rest.soup,
            self._select,
            self._attribute,
            self._index,
            self._value_template,
        )
        self._state = value

        if self._sensor_attributes:
            self._attributes = {}

            for idx, sensor_attribute in enumerate(self._sensor_attributes):

                name = sensor_attribute.get(CONF_NAME)

                select = sensor_attribute.get(CONF_SELECT)
                if select is not None:
                    select.hass = self._hass
                    select = select.async_render()
                _LOGGER.debug("Parsed sensor attribute select template: %s", select)

                select_attr = sensor_attribute.get(CONF_ATTR)
                index = sensor_attribute.get(CONF_INDEX)
                value_template = sensor_attribute.get(CONF_VALUE_TEMPLATE)
                attr_value = self._scrape(
                    self.rest.soup, select, select_attr, index, value_template
                )

                self._attributes[name] = attr_value

                _LOGGER.debug("Sensor attr %s scrape value: %s", name, attr_value)
