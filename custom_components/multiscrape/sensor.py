"""Support for Multiscrape sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
from homeassistant.const import CONF_ICON
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.typing import DiscoveryInfoType
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
ENTITY_ID_FORMAT = Platform.SENSOR + ".{}"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the multiscrape sensor."""
    # Must update the sensor now (including fetching the scraper resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, scraper = await async_get_config_and_coordinator(
            hass, Platform.SENSOR, discovery_info
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
        self._attr_available = True

        try:
            if self.coordinator.update_error is True:
                raise ValueError("Skipped scraping because data couldn't be updated")

            value = self.scraper.scrape(self._sensor_selector, self._name)
            _LOGGER.debug(
                "%s # %s # Selected: %s", self.scraper.name, self._name, value
            )

            if self.device_class not in {
                SensorDeviceClass.DATE,
                SensorDeviceClass.TIMESTAMP,
            }:
                self._attr_native_value = value

            else:
                self._attr_native_value = async_parse_date_datetime(
                    value, self.entity_id, self.device_class
                )
        except Exception as exception:
            self.coordinator.notify_scrape_exception()

            if self._sensor_selector.on_error.log not in [False, "false", "False"]:
                level = LOG_LEVELS[self._sensor_selector.on_error.log]
                _LOGGER.log(
                    level,
                    "%s # %s # Unable to scrape data: %s \nConsider using debug logging and log_response for further investigation.",
                    self.scraper.name,
                    self._name,
                    exception,
                )

            if self._sensor_selector.on_error.value == CONF_ON_ERROR_VALUE_NONE:
                self._attr_available = False
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
                if self._attr_native_value is None:
                    self._attr_available = False
                return
            elif self._sensor_selector.on_error.value == CONF_ON_ERROR_VALUE_DEFAULT:
                self._attr_native_value = self._sensor_selector.on_error_default
                _LOGGER.debug(
                    "%s # %s # On-error, set default value: %s",
                    self.scraper.name,
                    self._name,
                    self._sensor_selector.on_error_default,
                )
        # determine icon after exception so it's also set for on_error cases
        if self._icon_template:
            self._set_icon(self._attr_native_value)
