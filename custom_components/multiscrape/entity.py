"""The base entity for the scraper component."""
import logging
from abc import abstractmethod
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ON_ERROR_VALUE_DEFAULT
from .const import CONF_ON_ERROR_VALUE_LAST
from .const import CONF_ON_ERROR_VALUE_NONE
from .const import LOG_LEVELS
from .scraper import Scraper

_LOGGER = logging.getLogger(__name__)


class MultiscrapeEntity(Entity):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(
        self,
        hass,
        coordinator: DataUpdateCoordinator[Any],
        scraper: Scraper,
        name,
        device_class,
        resource_template,
        force_update,
        icon_template,
        picture,
        attribute_selectors,
    ) -> None:
        """Create the entity that may have a coordinator."""

        self.coordinator = coordinator
        self.scraper = scraper
        self._name = name

        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_force_update = force_update
        self._attr_should_poll = False
        self._attr_extra_state_attributes = {}
        self._attr_entity_picture = picture

        self._hass = hass
        self._attribute_selectors = attribute_selectors
        self._resource_template = resource_template
        self._icon_template = icon_template
        if self._icon_template:
            self._icon_template.hass = hass

        super().__init__()

    def _set_icon(self, value):
        self._attr_icon = self._icon_template.async_render(
            variables={"value": value}, parse_result=False
        )
        _LOGGER.debug("Icon template rendered and set to: %s", self._attr_icon)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_sensor()
        self._update_attributes()
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.last_update_success:
            self._attr_available = False
        else:
            self._attr_available = self.scraper.data is not None
            self._update_sensor()
            self._update_attributes()
        self.async_write_ha_state()

    @abstractmethod
    def _update_sensor(self):
        """Update state from the scraper data."""

    def _update_attributes(self):
        if self._attribute_selectors:
            self.old_attributes, self._attr_extra_state_attributes = (
                self._attr_extra_state_attributes,
                {},
            )
            for name, attr_selector in self._attribute_selectors.items():
                try:
                    attr_value = self.scraper.scrape(attr_selector)
                    self._attr_extra_state_attributes[name] = attr_value
                    _LOGGER.debug(
                        "Sensor %s attribute %s scraped value: %s",
                        self._name,
                        name,
                        attr_value,
                    )
                except Exception as exception:
                    _LOGGER.debug("Exception selecting sensor data: %s", exception)

                    if attr_selector.on_error.log in LOG_LEVELS.keys():
                        level = LOG_LEVELS[attr_selector.on_error.log]
                        _LOGGER.log(
                            level,
                            "Sensor %s attribute %s was unable to extract data from HTML",
                            self._name,
                            name,
                        )

                    if attr_selector.on_error.value == CONF_ON_ERROR_VALUE_NONE:
                        self._attr_extra_state_attributes[name] = None
                    elif attr_selector.on_error.value == CONF_ON_ERROR_VALUE_LAST:
                        self._attr_extra_state_attributes[
                            name
                        ] = self.old_attributes.get(name)
                    elif attr_selector.on_error.value == CONF_ON_ERROR_VALUE_DEFAULT:
                        self._attr_extra_state_attributes[
                            name
                        ] = attr_selector.on_error_default
