"""The base entity for the scraper component."""
import logging
from abc import abstractmethod
from typing import Any

from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (CONF_ON_ERROR_VALUE_DEFAULT, CONF_ON_ERROR_VALUE_LAST,
                    CONF_ON_ERROR_VALUE_NONE, LOG_LEVELS)
from .scraper import Scraper

_LOGGER = logging.getLogger(__name__)


class MultiscrapeEntity(RestoreEntity):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(
        self,
        hass,
        coordinator: DataUpdateCoordinator[Any],
        scraper: Scraper,
        name,
        device_class,
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
        if picture:
            self._attr_entity_picture = picture
            _LOGGER.debug(
                "%s # %s # Set picture to: %s",
                self.scraper.name,
                self._name,
                self._attr_entity_picture,
            )

        self.hass = hass
        self._attribute_selectors = attribute_selectors

        self._icon_template = icon_template
        if self._icon_template:
            self._icon_template.hass = hass

        super().__init__()

    def _set_icon(self, value):
        try:
            self._attr_icon = self._icon_template.async_render(
                variables={"value": value}, parse_result=False
            )
            _LOGGER.debug(
                "%s # %s # Icon template rendered and set to: %s",
                self.scraper.name,
                self._name,
                self._attr_icon,
            )
        except TemplateError as exception:
            _LOGGER.error(
                "%s # %s # Exception occurred when rendering icon template. Exception: %s",
                self.scraper.name,
                self._name,
                exception,
            )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "%s # %s # Added sensor to HA",
            self.scraper.name,
            self._name,
        )
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(
                    self._handle_coordinator_update)
            )

        if not (state := await self.async_get_last_state()):
            return
        _LOGGER.debug("%s # %s # Restoring previous state: %s", self.scraper.name, self._name, state.state)
        self._attr_native_value = state.state

        for name in self._attribute_selectors:
            if state.attributes.get(name) is not None:
                _LOGGER.debug("%s # %s # Restoring attribute `%s` with value: %s", self.scraper.name, self._name, name, state.attributes[name])
                self._attr_extra_state_attributes[name] = state.attributes[name]


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.last_update_success:
            _LOGGER.debug(
                "%s # %s # Last update of the resource was not successful. Setting sensor availability to False",
                self.scraper.name,
                self._name,
            )
            self._attr_available = False
        else:
            self._attr_available = True
            self._update_sensor()
            self._update_attributes()
        self.async_write_ha_state()
        _LOGGER.debug(
            "%s # %s # Sensor updated and state written to HA",
            self.scraper.name,
            self._name,
        )

    @abstractmethod
    def _update_sensor(self):
        """Update state from the scraper data."""

    def _update_attributes(self):
        if self._attribute_selectors:
            _LOGGER.debug(
                "%s # %s # Start scraping attributes",
                self.scraper.name,
                self._name,
            )
            self.old_attributes, self._attr_extra_state_attributes = (
                self._attr_extra_state_attributes,
                {},
            )
            for name, attr_selector in self._attribute_selectors.items():
                try:
                    attr_value = self.scraper.scrape(
                        attr_selector, self._name, name, variables=self.coordinator.form_variables)
                    self._attr_extra_state_attributes[name] = attr_value
                except Exception as exception:
                    _LOGGER.debug(
                        "%s # %s # %s # Exception selecting attribute data: %s",
                        self.scraper.name,
                        self._name,
                        name,
                        exception,
                    )

                    if attr_selector.on_error.log in LOG_LEVELS:
                        level = LOG_LEVELS[attr_selector.on_error.log]
                        _LOGGER.log(
                            level,
                            "%s # %s # %s # Unable to extract data from HTML",
                            self.scraper.name,
                            self._name,
                            name,
                        )

                    if attr_selector.on_error.value == CONF_ON_ERROR_VALUE_NONE:
                        _LOGGER.debug(
                            "%s # %s # %s # On-error, set value to None",
                            self.scraper.name,
                            self._name,
                            name,
                        )
                        self._attr_extra_state_attributes[name] = None
                    elif attr_selector.on_error.value == CONF_ON_ERROR_VALUE_LAST:
                        self._attr_extra_state_attributes[
                            name
                        ] = self.old_attributes.get(name)
                        _LOGGER.debug(
                            "%s # %s # %s # On-error, keep old value: %s",
                            self.scraper.name,
                            self._name,
                            name,
                            self.old_attributes.get(name),
                        )
                    elif attr_selector.on_error.value == CONF_ON_ERROR_VALUE_DEFAULT:
                        self._attr_extra_state_attributes[
                            name
                        ] = attr_selector.on_error_default
                        _LOGGER.debug(
                            "%s # %s # %s # On-error, set default value: %s",
                            self.scraper.name,
                            self._name,
                            name,
                            attr_selector.on_error_default,
                        )
