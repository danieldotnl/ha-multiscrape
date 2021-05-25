import logging

from bs4 import BeautifulSoup
from homeassistant.components.rest.data import RestData
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_VALUE_TEMPLATE

from .const import CONF_ATTR
from .const import CONF_INDEX
from .const import CONF_SELECT
from .const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class ScrapedRestData(RestData):
    """Class for handling data retrieval and scraping the data"""

    def __init__(
        self,
        hass,
        method,
        resource,
        auth,
        headers,
        params,
        data,
        verify_ssl,
        selectors,
        parser,
        timeout=DEFAULT_TIMEOUT,
    ):

        super().__init__(
            hass,
            method,
            resource,
            auth,
            headers,
            params,
            data,
            verify_ssl,
            timeout=DEFAULT_TIMEOUT,
        )

        self.values = {}
        self._selectors = selectors
        self._parser = parser

    def scrape_data(self):
        result = BeautifulSoup(self.data, self._parser)
        result.prettify()

        for device, device_config in self._selectors.items():
            key = device
            name = device_config.get(CONF_NAME)
            select = device_config.get(CONF_SELECT)
            attr = device_config.get(CONF_ATTR)
            index = device_config.get(CONF_INDEX)
            value_template = device_config.get(CONF_VALUE_TEMPLATE)

            if select is not None:
                select.hass = self._hass
                select = select.async_render()

            try:
                if attr is not None:
                    value = result.select(select)[index][attr]
                else:
                    tag = result.select(select)[index]
                    if tag.name in ("style", "script", "template"):
                        value = tag.string
                    else:
                        value = tag.text

                _LOGGER.debug("Sensor %s selected: %s", name, value)
            except IndexError as exception:
                _LOGGER.error("Sensor %s was unable to extract data from HTML", name)
                _LOGGER.debug("Exception: %s", exception)
                return

            if value_template is not None:
                value_template.hass = self._hass

                try:
                    self.values[
                        key
                    ] = value_template.async_render_with_possible_json_value(
                        value, None
                    )
                except Exception as exception:
                    _LOGGER.error(exception)

            else:
                self.values[key] = value

    async def async_update(self, log_errors=True):
        await super().async_update(log_errors)
        self.scrape_data()
