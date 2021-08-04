"""The base entity for the scraper component."""
import logging
from abc import abstractmethod
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
    ) -> None:
        """Create the entity that may have a coordinator."""

        self.coordinator = coordinator
        self.scraper = scraper
        self._name = name
        self._device_class = device_class
        self._resource_template = resource_template
        self._force_update = force_update

        self._hass = hass
        self._icon = None
        self._icon_template = icon_template
        if self._icon_template:
            self._icon_template.hass = hass
        self._unique_id = None

        super().__init__()

    @property
    def unique_id(self):
        """Return the unique id of this sensor."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    def _set_icon(self, value):
        self._icon = self._icon_template.async_render_with_possible_json_value(
            value, None
        )
        _LOGGER.debug("Icon template rendered and set to: %s", self._icon)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def should_poll(self) -> bool:
        """Poll only if we do noty have a coordinator."""
        return not self.coordinator

    @property
    def available(self):
        """Return the availability of this sensor."""
        if self.coordinator and not self.coordinator.last_update_success:
            return False
        return self.scraper.data is not None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_from_scraper_data()
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_scraper_data()
        self.async_write_ha_state()

    async def async_update(self):
        """Get the latest data from scraper resource and update the state."""
        if self.coordinator:
            await self.coordinator.async_request_refresh()
            return

        if self._resource_template is not None:
            self.scraper.set_url(
                self._resource_template.async_render(parse_result=False)
            )
        await self.scraper.async_update()
        self._update_from_scraper_data()

    @abstractmethod
    def _update_from_scraper_data(self):
        """Update state from the scraper data."""
