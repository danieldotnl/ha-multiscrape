"""Support for Multiscrape sensors."""
import logging

from homeassistant.components.rest.const import CONF_JSON_ATTRS
from homeassistant.components.rest.const import CONF_JSON_ATTRS_PATH
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
from . import create_rest_data_from_config
from .const import CONF_ATTR
from .const import CONF_INDEX
from .const import CONF_SELECT
from .entity import RestEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the RESTful sensor."""
    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, rest = await async_get_config_and_coordinator(
            hass, SENSOR_DOMAIN, discovery_info
        )
    else:
        conf = config
        coordinator = None
        rest = create_rest_data_from_config(hass, conf)
        await rest.async_update(log_errors=False)

    if rest.data is None:
        if rest.last_exception:
            raise PlatformNotReady from rest.last_exception
        raise PlatformNotReady

    name = conf.get(CONF_NAME)
    unit = conf.get(CONF_UNIT_OF_MEASUREMENT)
    device_class = conf.get(CONF_DEVICE_CLASS)
    json_attrs = conf.get(CONF_JSON_ATTRS)
    json_attrs_path = conf.get(CONF_JSON_ATTRS_PATH)
    select = conf.get(CONF_SELECT)
    attribute = conf.get(CONF_ATTR)
    index = conf.get(CONF_INDEX)
    value_template = conf.get(CONF_VALUE_TEMPLATE)
    force_update = conf.get(CONF_FORCE_UPDATE)
    resource_template = conf.get(CONF_RESOURCE_TEMPLATE)

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
                json_attrs,
                force_update,
                resource_template,
                json_attrs_path,
                select,
                attribute,
                index,
            )
        ],
    )


class RestSensor(RestEntity, SensorEntity):
    """Implementation of a REST sensor."""

    def __init__(
        self,
        hass,
        coordinator,
        rest,
        name,
        unit_of_measurement,
        device_class,
        value_template,
        json_attrs,
        force_update,
        resource_template,
        json_attrs_path,
        select,
        attribute,
        index,
    ):
        """Initialize the REST sensor."""
        super().__init__(
            coordinator, rest, name, device_class, resource_template, force_update
        )
        self._state = None
        self._hass = hass
        self._unit_of_measurement = unit_of_measurement
        self._value_template = value_template
        self._json_attrs = json_attrs
        self._attributes = None
        self._json_attrs_path = json_attrs_path
        self._select = select
        self._attribute = attribute
        self._index = index

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
        value = self.rest.soup
        # _LOGGER.debug("Data fetched from resource: %s", value)

        if self._select is not None:
            self._select.hass = self._hass
            select = self._select.async_render()

        _LOGGER.debug("Parsed select template: %s", select)

        try:
            if self._attribute is not None:
                value = value.select(select)[self._index][self._attribute]
            else:
                tag = value.select(select)[self._index]
                if tag.name in ("style", "script", "template"):
                    value = tag.string
                else:
                    value = tag.text

            _LOGGER.debug("Sensor %s selected: %s", self._name, value)
        except IndexError as exception:
            _LOGGER.error("Sensor %s was unable to extract data from HTML", self._name)
            _LOGGER.debug("Exception: %s", exception)
            return

        if value is not None and self._value_template is not None:
            value = self._value_template.async_render_with_possible_json_value(
                value, None
            )

        self._state = value
