"""Support for Multiscrape sensors."""
import logging

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
from homeassistant.const import CONF_ICON
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_RESOURCE_TEMPLATE
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
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

_LOGGER = logging.getLogger(__name__)
ENTITY_ID_FORMAT = SENSOR_DOMAIN + ".{}"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the multiscrape sensor."""
    # Must update the sensor now (including fetching the scraper resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, scraper = await async_get_config_and_coordinator(
            hass, SENSOR_DOMAIN, discovery_info
        )
    else:
        _LOGGER.error("Could not find sensor configuration")

    if scraper.data is None:
        if scraper.last_exception:
            raise PlatformNotReady from scraper.last_exception
        raise PlatformNotReady

    name = conf.get(CONF_NAME)
    unique_id = conf.get(CONF_UNIQUE_ID)
    unit = conf.get(CONF_UNIT_OF_MEASUREMENT)
    device_class = conf.get(CONF_DEVICE_CLASS)
    select_template = conf.get(CONF_SELECT)
    select_list_template = conf.get(CONF_SELECT_LIST)
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
            MultiscrapeSensor(
                hass,
                coordinator,
                scraper,
                unique_id,
                name,
                unit,
                device_class,
                value_template,
                force_update,
                resource_template,
                select_template,
                select_list_template,
                attribute,
                index,
                sensor_attributes,
                icon_template,
            )
        ],
    )


class MultiscrapeSensor(MultiscrapeEntity, SensorEntity):
    """Implementation of a multiscrape sensor."""

    def __init__(
        self,
        hass,
        coordinator,
        scraper,
        unique_id,
        name,
        unit_of_measurement,
        device_class,
        value_template,
        force_update,
        resource_template,
        select_template,
        select_list_template,
        attribute,
        index,
        sensor_attributes,
        icon_template,
    ):
        """Initialize the multiscrape sensor."""
        super().__init__(
            hass,
            coordinator,
            scraper,
            name,
            device_class,
            resource_template,
            force_update,
            icon_template,
        )
        self._state = None
        self._attr_unit_of_measurement = unit_of_measurement
        self._value_template = value_template
        self._attributes = None
        self._select_template = select_template
        self._select_list_template = select_list_template
        self._attribute = attribute
        self._index = index
        self._sensor_attributes = sensor_attributes
        self._select = None
        self._select_list = None

        self._attr_unique_id = unique_id

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, unique_id or name, hass=hass
        )

        if self._select_template is not None:
            self._select_template.hass = self._hass
        if self._select_list_template is not None:
            self._select_list_template.hass = self._hass

    def _update_from_scraper_data(self):
        """Update state from the scraper data."""

        if self._select_template:
            self._select = self._select_template.async_render(parse_result=True)
            _LOGGER.debug("Rendered select template: %s", self._select)
        elif self._select_list_template:
            self._select_list = self._select_list_template.async_render(
                parse_result=True
            )
            _LOGGER.debug("Rendered select template: %s", self._select_list)
        else:
            raise ValueError(
                "State selector error: either select or select_list should contain a selector."
            )

        try:
            value = self.scraper.scrape(
                self._select,
                self._select_list,
                self._attribute,
                self._index,
                self._value_template,
            )
            _LOGGER.debug("Sensor %s selected: %s", self._name, value)
            self._attr_state = value
        except Exception as exception:
            self._attr_state = None
            _LOGGER.error("Sensor %s was unable to extract data from HTML", self._name)
            _LOGGER.debug("Exception: %s", exception)

        if self._icon_template:
            self._set_icon(value)

        if self._sensor_attributes:
            self._attr_extra_state_attributes = {}

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

                attr_value = self.scraper.scrape(
                    select,
                    select_list,
                    select_attr,
                    index,
                    value_template,
                )

                self._attr_extra_state_attributes[name] = attr_value

                _LOGGER.debug("Sensor attr %s scrape value: %s", name, attr_value)
