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
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify

from . import async_get_config_and_coordinator
from .const import CONF_ON_ERROR_VALUE_DEFAULT
from .const import CONF_ON_ERROR_VALUE_LAST
from .const import CONF_ON_ERROR_VALUE_NONE
from .const import CONF_PICTURE
from .const import CONF_SENSOR_ATTRS
from .const import CONF_STATE_CLASS
from .const import LOG_LEVELS
from .entity import MultiscrapeEntity
from .selector import Selector

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
        _LOGGER.info("?? # Could not find sensor configuration")

    if not coordinator.last_update_success:
        raise PlatformNotReady

    sensor_name = conf.get(CONF_NAME)
    _LOGGER.debug("%s # %s # Setting up sensor", scraper.name, sensor_name)
    unique_id = conf.get(CONF_UNIQUE_ID)
    unit = conf.get(CONF_UNIT_OF_MEASUREMENT)
    device_class = conf.get(CONF_DEVICE_CLASS)
    state_class = conf.get(CONF_STATE_CLASS)
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
            MultiscrapeSensor(
                hass,
                coordinator,
                scraper,
                unique_id,
                sensor_name,
                unit,
                device_class,
                state_class,
                force_update,
                resource_template,
                icon_template,
                picture,
                sensor_selector,
                attribute_selectors,
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
        state_class,
        force_update,
        resource_template,
        icon_template,
        picture,
        sensor_selector,
        attribute_selectors,
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
            picture,
            attribute_selectors,
        )

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, unique_id or name, hass=hass
        )
        self._attr_unique_id = unique_id
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit_of_measurement

        self._sensor_selector = sensor_selector

    def _update_sensor(self):
        """Update state from the scraper data."""
        _LOGGER.debug(
            "%s # %s # Start scraping to update sensor", self.scraper.name, self._name
        )

        try:
            value = self.scraper.scrape(self._sensor_selector, self._name)
            _LOGGER.debug(
                "%s # %s # Selected: %s", self.scraper.name, self._name, value
            )
            self._attr_native_value = value

            if self._icon_template:
                self._set_icon(value)
        except Exception as exception:
            self.coordinator.notify_scrape_exception()

            if self._sensor_selector.on_error.log not in [False, "false", "False"]:
                level = LOG_LEVELS[self._sensor_selector.on_error.log]
                _LOGGER.log(
                    level,
                    "%s # %s # Unable to scrape data: %s. \nConsider using debug logging and log_response for further investigation.",
                    self.scraper.name,
                    self._name,
                    exception,
                )

            if self._sensor_selector.on_error.value == CONF_ON_ERROR_VALUE_NONE:
                self._attr_native_value = None
                _LOGGER.debug(
                    "%s # %s # On-error, set value to None",
                    self.scraper.name,
                    self._name,
                )
            elif self._sensor_selector.on_error.value == CONF_ON_ERROR_VALUE_LAST:
                _LOGGER.debug(
                    "%s # %s # On-error, keep old value: %s",
                    self.scraper.name,
                    self._name,
                    self._attr_native_value,
                )
                return
            elif self._sensor_selector.on_error.value == CONF_ON_ERROR_VALUE_DEFAULT:
                self._attr_native_value = self._sensor_selector.on_error_default
                _LOGGER.debug(
                    "%s # %s # On-error, set default value: %s",
                    self.scraper.name,
                    self._name,
                    self._sensor_selector.on_error_default,
                )
