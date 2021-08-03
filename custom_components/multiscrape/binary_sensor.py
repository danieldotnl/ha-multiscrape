"""Support for multiscrape binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
from homeassistant.const import CONF_ICON
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_RESOURCE_TEMPLATE
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify

from . import async_get_config_and_coordinator
from .const import CONF_ATTR
from .const import CONF_INDEX
from .const import CONF_SELECT
from .const import CONF_SELECT_LIST
from .const import CONF_SENSOR_ATTRS
from .entity import MultiscrapeEntity

ENTITY_ID_FORMAT = BINARY_SENSOR_DOMAIN + ".{}"
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the multiscrape binary sensor."""
    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, rest = await async_get_config_and_coordinator(
            hass, BINARY_SENSOR_DOMAIN, discovery_info
        )
    else:
        _LOGGER.error("Could not find sensor configuration")

    if rest.data is None:
        if rest.last_exception:
            raise PlatformNotReady from rest.last_exception
        raise PlatformNotReady

    name = conf.get(CONF_NAME)
    unique_id = conf.get(CONF_UNIQUE_ID)
    device_class = conf.get(CONF_DEVICE_CLASS)
    select = conf.get(CONF_SELECT)
    attribute = conf.get(CONF_ATTR)
    index = conf.get(CONF_INDEX)
    value_template = conf.get(CONF_VALUE_TEMPLATE)
    force_update = conf.get(CONF_FORCE_UPDATE)
    resource_template = conf.get(CONF_RESOURCE_TEMPLATE)
    sensor_attributes = conf.get(CONF_SENSOR_ATTRS)
    icon_template = conf.get(CONF_ICON)

    if value_template is not None:
        value_template.hass = hass

    async_add_entities(
        [
            MultiscrapeBinarySensor(
                hass,
                coordinator,
                rest,
                unique_id,
                name,
                device_class,
                value_template,
                force_update,
                resource_template,
                select,
                attribute,
                index,
                sensor_attributes,
                icon_template,
            )
        ],
    )


class MultiscrapeBinarySensor(MultiscrapeEntity, BinarySensorEntity):
    """Representation of a multiscrape binary sensor."""

    def __init__(
        self,
        hass,
        coordinator,
        rest,
        unique_id,
        name,
        device_class,
        value_template,
        force_update,
        resource_template,
        select_template,
        attribute,
        index,
        sensor_attributes,
        icon_template,
    ):

        """Initialize a multiscrape binary sensor."""
        super().__init__(
            hass,
            coordinator,
            rest,
            name,
            device_class,
            resource_template,
            force_update,
            icon_template,
        )
        self._state = False
        self._previous_data = None
        self._value_template = value_template
        self._is_on = None
        self._unique_id = unique_id
        self._select_template = select_template
        self._attribute = attribute
        self._index = index
        self._attributes = None
        self._sensor_attributes = sensor_attributes

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, unique_id or name, hass=hass
        )

        if self._select_template is not None:
            self._select_template.hass = self._hass

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    def _update_from_rest_data(self):
        """Update state from the scraped data."""

        self._select = self._select_template.async_render(parse_result=False)
        _LOGGER.debug("Parsed select template: %s", self._select)

        if self.rest.soup is None:
            self._is_on = False

        value = self._scrape(
            self.rest.soup,
            self._select,
            None,
            self._attribute,
            self._index,
            self._value_template,
        )

        try:
            self._is_on = bool(int(value))
        except ValueError:
            self._is_on = {"true": True, "on": True, "open": True, "yes": True}.get(
                value.lower(), False
            )

        if self._icon_template:
            self._set_icon(self._is_on)

        if self._sensor_attributes:
            self._attributes = {}

            for idx, sensor_attribute in enumerate(self._sensor_attributes):

                name = slugify(sensor_attribute.get(CONF_NAME))

                select = sensor_attribute.get(CONF_SELECT)
                select_list = sensor_attribute.get(CONF_SELECT_LIST)

                if select is not None:
                    select.hass = self._hass
                    select = select.render(parse_result=False)
                    _LOGGER.debug("Parsed sensor attribute select template: %s", select)

                elif select_list is not None:
                    select_list.hass = self._hass
                    select_list = select_list.render(parse_result=False)
                    _LOGGER.debug(
                        "Parsed sensor attribute select template: %s", select_list
                    )

                else:
                    raise ValueError(
                        "Attribute selector error: either select or select_list should contain a selector."
                    )

                select_attr = sensor_attribute.get(CONF_ATTR)
                index = sensor_attribute.get(CONF_INDEX)
                value_template = sensor_attribute.get(CONF_VALUE_TEMPLATE)
                if value_template:
                    value_template.hass = self._hass
                attr_value = self._scrape(
                    self.rest.soup,
                    select,
                    select_list,
                    select_attr,
                    index,
                    value_template,
                )

                self._attributes[name] = attr_value

                _LOGGER.debug("Sensor attr %s scrape value: %s", name, attr_value)
