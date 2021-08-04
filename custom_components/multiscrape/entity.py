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

        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_force_update = force_update
        self._attr_should_poll = False

        self._hass = hass
        self._resource_template = resource_template
        self._icon_template = icon_template
        if self._icon_template:
            self._icon_template.hass = hass

        super().__init__()

    def _set_icon(self, value):
        self._attr_icon = self._icon_template.async_render_with_possible_json_value(
            value, None
        )
        _LOGGER.debug("Icon template rendered and set to: %s", self._attr_icon)

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
