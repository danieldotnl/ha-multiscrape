import logging

from bs4 import BeautifulSoup
from homeassistant.components.rest.data import DEFAULT_TIMEOUT
from homeassistant.components.rest.data import RestData

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
            timeout,
        )

        self._parser = parser
        self.soup = None

    async def async_update(self, log_errors=True):
        await super().async_update(log_errors)

        self.soup = BeautifulSoup(self.data, self._parser)
        self.soup.prettify()
