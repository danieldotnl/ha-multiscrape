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
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify

from . import async_get_config_and_coordinator
from .const import CONF_ON_ERROR_VALUE_DEFAULT
from .const import CONF_ON_ERROR_VALUE_LAST
from .const import CONF_ON_ERROR_VALUE_NONE
from .const import CONF_PICTURE
from .const import CONF_SENSOR_ATTRS
from .const import LOG_LEVELS
from .entity import MultiscrapeEntity
from .selector import Selector

ENTITY_ID_FORMAT = BINARY_SENSOR_DOMAIN + ".{}"
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the multiscrape binary sensor."""
    # Must update the sensor now (including fetching the scraper resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, scraper = await async_get_config_and_coordinator(
            hass, BINARY_SENSOR_DOMAIN, discovery_info
        )
    else:
        _LOGGER.info("Could not find binary_sensor configuration")

    if scraper.data is None:
        if scraper.last_exception:
            raise PlatformNotReady from scraper.last_exception
        raise PlatformNotReady

    name = conf.get(CONF_NAME)
    unique_id = conf.get(CONF_UNIQUE_ID)
    device_class = conf.get(CONF_DEVICE_CLASS)
    force_update = conf.get(CONF_FORCE_UPDATE)
    resource_template = conf.get(CONF_RESOURCE_TEMPLATE)
    icon_template = conf.get(CONF_ICON)
    picture = conf.get(CONF_PICTURE)

    sensor_selector = Selector(hass, conf)
    attribute_selectors = {}
    for attr_conf in conf.get(CONF_SENSOR_ATTRS) or []:
        attr_name = slugify(attr_conf[CONF_NAME])
        attribute_selectors[attr_name] = Selector(hass, attr_conf)

    async_add_entities(
        [
            MultiscrapeBinarySensor(
                hass,
                coordinator,
                scraper,
                unique_id,
                name,
                device_class,
                force_update,
                resource_template,
                icon_template,
                picture,
                sensor_selector,
                attribute_selectors,
            )
        ],
    )


class MultiscrapeBinarySensor(MultiscrapeEntity, BinarySensorEntity):
    """Representation of a multiscrape binary sensor."""

    def __init__(
        self,
        hass,
        coordinator,
        scraper,
        unique_id,
        name,
        device_class,
        force_update,
        resource_template,
        icon_template,
        picture,
        sensor_selector,
        attribute_selectors,
    ):

        """Initialize a multiscrape binary sensor."""
        super().__init__(
            hass,
            coordinator,
            scraper,
            name,
            device_class,
            resource_template,
            force_update,
            icon_template,
            picture,
            attribute_selectors,
        )

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, unique_id or name, hass=hass
        )

        self._attr_unique_id = unique_id
        self._sensor_selector = sensor_selector

    def _update_sensor(self):
        """Update state from the scraped data."""
        if self.scraper.soup is None:
            self._is_on = False

        try:
            value = self.scraper.scrape(self._sensor_selector)
            _LOGGER.debug("Sensor %s selected: %s", self._name, value)
            try:
                self._attr_is_on = bool(int(value))
            except ValueError:
                self._attr_is_on = {
                    "true": True,
                    "on": True,
                    "open": True,
                    "yes": True,
                }.get(value.lower(), False)

            if self._icon_template:
                self._set_icon(value)
        except Exception as exception:
            _LOGGER.debug("Exception selecting sensor data: %s", exception)

            if self._sensor_selector.on_error.log in LOG_LEVELS.keys():
                level = LOG_LEVELS[self._sensor_selector.on_error.log]
                _LOGGER.log(
                    level, "Sensor %s was unable to extract data from HTML", self._name
                )

            if self._sensor_selector.on_error.value == CONF_ON_ERROR_VALUE_NONE:
                self._attr_state = None
            elif self._sensor_selector.on_error.value == CONF_ON_ERROR_VALUE_LAST:
                return
            elif self._sensor_selector.on_error.value == CONF_ON_ERROR_VALUE_DEFAULT:
                self._attr_state = self._sensor_selector.on_error_default
