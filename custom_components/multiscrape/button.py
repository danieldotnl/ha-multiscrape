"""Support for Multiscrape refresh button."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity import EntityCategory

from . import async_get_config_and_coordinator

ENTITY_ID_FORMAT = BUTTON_DOMAIN + ".{}"
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities, discovery_info=None
):
    """Set up the multiscrape refresh button"""

    conf, coordinator, scraper = await async_get_config_and_coordinator(
        hass, BUTTON_DOMAIN, discovery_info
    )
    name = conf.get(CONF_NAME)
    unique_id = conf.get(CONF_UNIQUE_ID)

    async_add_entities(
        [
            MultiscrapeRefreshButton(
                hass,
                coordinator,
                unique_id,
                name,
            )
        ]
    )


class MultiscrapeRefreshButton(ButtonEntity):
    """Multiscrape refresh button."""

    def __init__(self, hass, coordinator, unique_id, name):
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_name = name
        self._coordinator = coordinator

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, unique_id or name, hass=hass
        )

        self._attr_unique_id = unique_id

    async def async_press(self) -> None:
        """Press the button."""
        _LOGGER.info("Multiscrape triggered by button")
        await self._coordinator.async_request_refresh()
