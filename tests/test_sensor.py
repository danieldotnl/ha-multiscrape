"""Tests for multiscrape sensor."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.multiscrape.const import DOMAIN

from . import MockHttpWrapper


async def test_scrape_html(hass: HomeAssistant) -> None:
    """Test the scrape sensor."""
    config = {
        "multiscrape": {
              "name": "HA scraper",
              "resource": "https://www.home-assistant.io",
              "scan_interval": 3600,
              "sensor": [
                  {
                        "unique_id": "ha_latest_version",
                        "name": "Latest version",
                        "select": ".current-version h1",
                        "value_template": "{{ value.split(': ')[1] }}",
                  }
            ]
        }

    }

    mocker = MockHttpWrapper("simple_html")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.ha_latest_version")
        assert state.state == "2024.8.3"

async def test_scrape_json(hass: HomeAssistant) -> None:
    """Test the scrape sensor."""
    config = {
        "multiscrape": {
              "name": "HA scraper",
              "resource": "https://www.home-assistant.io",
              "scan_interval": 3600,
              "sensor": [
                  {
                        "unique_id": "json_test_age",
                        "value_template": "{{ value_json.age }}",
                  }
            ]
        }

    }

    mocker = MockHttpWrapper("simple_json")
    with patch(
        "custom_components.multiscrape.http.HttpWrapper",
        return_value=mocker,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()


        state = hass.states.get("sensor.json_test_age")
        assert state.state == "30"
