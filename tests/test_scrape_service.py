"""Edge case tests for the multiscrape scrape service.

Core scrape service tests are in test_service.py. These tests cover
additional edge cases and error paths.
"""

import pytest
import respx
from homeassistant.const import CONF_RESOURCE, Platform
from homeassistant.core import HomeAssistant

from custom_components.multiscrape.const import CONF_PARSER, DOMAIN
from custom_components.multiscrape.service import setup_scrape_service


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_scrape_service_with_no_sensors(hass: HomeAssistant):
    """Test scrape service with no sensor or binary_sensor definitions.

    A valid config may omit all sensor definitions. The service should
    return an empty dict rather than failing.
    """
    await setup_scrape_service(hass)

    test_url = "https://example.com/data"
    html_content = "<html><body><div>Content</div></body></html>"
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text=html_content))

    service_data = {
        CONF_RESOURCE: test_url,
        CONF_PARSER: "html.parser",
    }

    response = await hass.services.async_call(
        DOMAIN, "scrape", service_data, blocking=True, return_response=True
    )

    assert response == {}


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_scrape_service_with_nonexistent_selector(hass: HomeAssistant):
    """Test scrape service when CSS selector matches nothing.

    The scraper should raise an exception for a selector that matches
    no elements, which propagates as a service call error.
    """
    await setup_scrape_service(hass)

    test_url = "https://example.com/data"
    html_content = "<html><body><div>Content</div></body></html>"
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text=html_content))

    service_data = {
        CONF_RESOURCE: test_url,
        CONF_PARSER: "html.parser",
        Platform.SENSOR: [
            {
                "name": "Missing",
                "unique_id": "missing_sensor",
                "select": ".does-not-exist",
            }
        ],
    }

    with pytest.raises(Exception):
        await hass.services.async_call(
            DOMAIN, "scrape", service_data, blocking=True, return_response=True
        )


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_scrape_service_with_value_template(hass: HomeAssistant):
    """Test scrape service with a value_template that transforms scraped value.

    Templates in service calls use the {!{ }!} placeholder syntax which gets
    restored to {{ }} before evaluation.
    """
    await setup_scrape_service(hass)

    test_url = "https://example.com/data"
    html_content = '<html><body><div class="temp">  23.5  </div></body></html>'
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text=html_content))

    service_data = {
        CONF_RESOURCE: test_url,
        CONF_PARSER: "html.parser",
        Platform.SENSOR: [
            {
                "name": "Temperature",
                "unique_id": "temp",
                "select": ".temp",
                "value_template": "{!{ value | trim }!}",
            }
        ],
    }

    response = await hass.services.async_call(
        DOMAIN, "scrape", service_data, blocking=True, return_response=True
    )

    # HA's template engine parses "23.5" to float 23.5 by default
    assert response["temp"]["value"] == 23.5
