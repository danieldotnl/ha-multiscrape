"""The base entity for the rest component."""
import logging
from typing import Any

from homeassistant.components.rest.entity import RestEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .data import RestData

_LOGGER = logging.getLogger(__name__)


class MultiscrapeEntity(RestEntity):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(
        self,
        hass,
        coordinator: DataUpdateCoordinator[Any],
        rest: RestData,
        name,
        device_class,
        resource_template,
        force_update,
        icon_template,
    ) -> None:
        """Create the entity that may have a coordinator."""

        super().__init__(
            coordinator,
            rest,
            name,
            device_class,
            resource_template,
            force_update,
        )

        self._hass = hass
        self._icon = None
        self._icon_template = icon_template
        if self._icon_template:
            self._icon_template.hass = hass
        self._unique_id = None

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
