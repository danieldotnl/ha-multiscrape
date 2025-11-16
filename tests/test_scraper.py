"""Tests for scraper class."""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import DEFAULT_SEPARATOR
from custom_components.multiscrape.scraper import Scraper
from custom_components.multiscrape.selector import Selector


@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scrape_extract_text(hass: HomeAssistant) -> None:
    """Test scraping and extract text method."""
    scraper = Scraper("test_scraper", hass, None, "lxml", DEFAULT_SEPARATOR)
    await scraper.set_content(
        "<div class='current-version material-card text'>"
                        "<h1>Current Version: 2024.8.3</h1>Released: <span class='release-date'>January 17, 2022</span>"
                        "<div class='links' style='links'><a href='/latest-release-notes/'>Release notes</a>"
                        "</div>"
                    "</div>"
                    "<template>Trying to get</template>"
                    "<div class='current-time'>"
                        "<h1>Current Time:</h1><span class='utc-time'>2022-12-22T13:15:30Z</span>"
                    "</div>"
    )

    selector_conf = {
        "select": Template(".current-version h1", hass),
        "extract": "text",
    }

    selector = Selector(hass, selector_conf)
    value = scraper.scrape(selector, "test_sensor")
    assert value == "Current Version: 2024.8.3"

@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scrape_extract_content(hass: HomeAssistant) -> None:
    """Test scraping and extract contents method."""
    scraper = Scraper("test_scraper", hass, None, "lxml", DEFAULT_SEPARATOR)
    await scraper.set_content(
        "<div class='current-version material-card text'>"
                        "<h1>Current Version: 2024.8.3</h1>Released: <span class='release-date'>January 17, 2022</span>"
                        "<div class='links' style='links'><a href='/latest-release-notes/'>Release notes</a>"
                        "</div>"
                    "</div>"
                    "<template>Trying to get</template>"
                    "<div class='current-time'>"
                        "<h1>Current Time:</h1><span class='utc-time'>2022-12-22T13:15:30Z</span>"
                    "</div>"
    )

    selector_conf = {
        "select": Template(".links", hass),
        "extract": "content",
    }

    selector = Selector(hass, selector_conf)
    value = scraper.scrape(selector, "test_sensor")
    assert value == '<a href="/latest-release-notes/">Release notes</a>'

@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scrape_extract_tag(hass: HomeAssistant) -> None:
    """Test scraping and extract tag method."""
    scraper = Scraper("test_scraper", hass, None, "lxml", DEFAULT_SEPARATOR)
    await scraper.set_content(
        "<div class='current-version material-card text'>"
                        "<h1>Current Version: 2024.8.3</h1>Released: <span class='release-date'>January 17, 2022</span>"
                        "<div class='links' style='links'><a href='/latest-release-notes/'>Release notes</a>"
                        "</div>"
                    "</div>"
                    "<template>Trying to get</template>"
                    "<div class='current-time'>"
                        "<h1>Current Time:</h1><span class='utc-time'>2022-12-22T13:15:30Z</span>"
                    "</div>"
    )

    selector_conf = {
        "select": Template(".links", hass),
        "extract": "tag",
    }

    selector = Selector(hass, selector_conf)
    value = scraper.scrape(selector, "test_sensor")
    assert value == '<div class="links" style="links"><a href="/latest-release-notes/">Release notes</a></div>'

@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_scrape_extract_attribute(hass: HomeAssistant) -> None:
    """Test scraping and extract an HTML attribute value."""
    scraper = Scraper("test_scraper", hass, None, "lxml", DEFAULT_SEPARATOR)
    await scraper.set_content(
        "<div class='current-version material-card text'>"
                        "<h1>Current Version: 2024.8.3</h1>Released: <span class='release-date'>January 17, 2022</span>"
                        "<div class='links' style='links'><a href='/latest-release-notes/'>Release notes</a>"
                        "</div>"
                    "</div>"
                    "<template>Trying to get</template>"
                    "<div class='current-time'>"
                        "<h1>Current Time:</h1><span class='utc-time'>2022-12-22T13:15:30Z</span>"
                    "</div>"
    )

    selector_conf = {
        "select": Template(".links a", hass),
        "attribute": "href",
    }

    selector = Selector(hass, selector_conf)
    value = scraper.scrape(selector, "test_sensor")
    assert value == '/latest-release-notes/'




