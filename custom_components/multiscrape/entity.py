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

    def _scrape(self, content, select, attribute, index, value_template):

        try:
            if attribute is not None:
                value = content.select(select)[index][attribute]
            else:
                tag = content.select(select)[index]
                if tag.name in ("style", "script", "template"):
                    value = tag.string
                else:
                    value = tag.text

            _LOGGER.debug("Sensor %s selected: %s", self._name, value)
        except IndexError as exception:
            self.rest.notify_scrape_exception()
            _LOGGER.error("Sensor %s was unable to extract data from HTML", self._name)
            _LOGGER.debug("Exception: %s", exception)
            return

        if value is not None and value_template is not None:
            value = value_template.async_render_with_possible_json_value(value, None)

        return value
