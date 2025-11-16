"""Integration tests for HTTP async request functionality."""

import pytest
import respx
from homeassistant.const import HTTP_DIGEST_AUTHENTICATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from httpx import RequestError, TimeoutException

from custom_components.multiscrape.http import HttpWrapper


@pytest.fixture
async def http_wrapper_basic(hass: HomeAssistant):
    """Create a basic HttpWrapper instance for testing."""
    from custom_components.multiscrape.util import (create_dict_renderer,
                                                    create_renderer)

    client = get_async_client(hass, verify_ssl=True)
    wrapper = HttpWrapper(
        config_name="test_wrapper",
        hass=hass,
        client=client,
        file_manager=None,
        timeout=10,
        params_renderer=create_dict_renderer(hass, None),
        headers_renderer=create_dict_renderer(hass, None),
        data_renderer=create_renderer(hass, None),
    )
    return wrapper


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_basic_get_request(http_wrapper_basic):
    """Test basic GET request returns response text."""
    # Arrange
    test_url = "https://example.com/test"
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text="Success"))

    # Act
    response = await http_wrapper_basic.async_request("test", test_url)

    # Assert
    assert response.text == "Success"
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_post_request(http_wrapper_basic):
    """Test POST request with data."""
    # Arrange
    test_url = "https://example.com/api"
    respx.post(test_url).mock(return_value=respx.MockResponse(201, text="Created"))

    # Act
    response = await http_wrapper_basic.async_request(
        "test", test_url, method="POST", request_data="test_data"
    )

    # Assert
    assert response.text == "Created"
    assert response.status_code == 201


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_with_headers(hass: HomeAssistant):
    """Test request with custom headers."""
    from custom_components.multiscrape.util import (create_dict_renderer,
                                                    create_renderer)

    # Arrange
    client = get_async_client(hass, verify_ssl=True)
    headers_renderer = lambda vars: {"Authorization": "Bearer token", "Custom": "Header"}

    wrapper = HttpWrapper(
        config_name="test",
        hass=hass,
        client=client,
        file_manager=None,
        timeout=10,
        headers_renderer=headers_renderer,
        params_renderer=create_dict_renderer(hass, None),
        data_renderer=create_renderer(hass, None),
    )

    test_url = "https://example.com/protected"
    route = respx.get(test_url).mock(return_value=respx.MockResponse(200, text="OK"))

    # Act
    await wrapper.async_request("test", test_url)

    # Assert
    assert route.called
    assert route.calls.last.request.headers["Authorization"] == "Bearer token"
    assert route.calls.last.request.headers["Custom"] == "Header"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_with_basic_auth(hass: HomeAssistant):
    """Test request with basic authentication."""
    from custom_components.multiscrape.util import (create_dict_renderer,
                                                    create_renderer)

    # Arrange
    client = get_async_client(hass, verify_ssl=True)
    wrapper = HttpWrapper(
        config_name="test",
        hass=hass,
        client=client,
        file_manager=None,
        timeout=10,
        params_renderer=create_dict_renderer(hass, None),
        headers_renderer=create_dict_renderer(hass, None),
        data_renderer=create_renderer(hass, None),
    )
    wrapper.set_authentication("testuser", "testpass", None)

    test_url = "https://example.com/auth"
    route = respx.get(test_url).mock(return_value=respx.MockResponse(200, text="Authenticated"))

    # Act
    response = await wrapper.async_request("test", test_url)

    # Assert
    assert response.text == "Authenticated"
    assert route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_with_digest_auth(hass: HomeAssistant):
    """Test request with digest authentication."""
    from custom_components.multiscrape.util import (create_dict_renderer,
                                                    create_renderer)

    # Arrange
    client = get_async_client(hass, verify_ssl=True)
    wrapper = HttpWrapper(
        config_name="test",
        hass=hass,
        client=client,
        file_manager=None,
        timeout=10,
        params_renderer=create_dict_renderer(hass, None),
        headers_renderer=create_dict_renderer(hass, None),
        data_renderer=create_renderer(hass, None),
    )
    wrapper.set_authentication("testuser", "testpass", HTTP_DIGEST_AUTHENTICATION)

    test_url = "https://example.com/digest"
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text="Digest OK"))

    # Act
    response = await wrapper.async_request("test", test_url)

    # Assert
    assert response.text == "Digest OK"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_http_wrapper_with_cookies(http_wrapper_basic):
    """Test request with cookies.

    Note: We use per-request cookies because they come from form submissions.
    The deprecation warning is expected and acceptable for this use case.
    """
    # Arrange
    test_url = "https://example.com/session"
    respx.get(test_url).mock(return_value=respx.MockResponse(200, text="Session OK"))

    cookies = {"session_id": "abc123", "user": "test"}

    # Act
    response = await http_wrapper_basic.async_request("test", test_url, cookies=cookies)

    # Assert
    assert response.text == "Session OK"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_follows_redirects(http_wrapper_basic):
    """Test that wrapper follows redirects."""
    # Arrange
    original_url = "https://example.com/redirect"
    final_url = "https://example.com/final"

    respx.get(original_url).mock(
        return_value=respx.MockResponse(302, headers={"Location": final_url})
    )
    respx.get(final_url).mock(return_value=respx.MockResponse(200, text="Final page"))

    # Act
    response = await http_wrapper_basic.async_request("test", original_url)

    # Assert
    assert response.status_code == 200
    assert response.text == "Final page"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_handles_404_error(http_wrapper_basic):
    """Test that wrapper raises exception on 404 error."""
    # Arrange
    test_url = "https://example.com/notfound"
    respx.get(test_url).mock(return_value=respx.MockResponse(404, text="Not Found"))

    # Act & Assert
    with pytest.raises(Exception):  # httpx will raise for 4xx/5xx
        await http_wrapper_basic.async_request("test", test_url)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_handles_500_error(http_wrapper_basic):
    """Test that wrapper raises exception on 500 error."""
    # Arrange
    test_url = "https://example.com/error"
    respx.get(test_url).mock(return_value=respx.MockResponse(500, text="Server Error"))

    # Act & Assert
    with pytest.raises(Exception):
        await http_wrapper_basic.async_request("test", test_url)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_handles_timeout(http_wrapper_basic):
    """Test that wrapper properly handles timeout exceptions."""
    # Arrange
    test_url = "https://example.com/slow"
    respx.get(test_url).mock(side_effect=TimeoutException("Request timed out"))

    # Act & Assert
    with pytest.raises(TimeoutException):
        await http_wrapper_basic.async_request("test", test_url)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_handles_connection_error(http_wrapper_basic):
    """Test that wrapper handles connection errors."""
    # Arrange
    test_url = "https://example.com/unreachable"
    respx.get(test_url).mock(side_effect=RequestError("Connection failed"))

    # Act & Assert
    with pytest.raises(RequestError):
        await http_wrapper_basic.async_request("test", test_url)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_with_params_renderer(hass: HomeAssistant):
    """Test request with params renderer."""
    from custom_components.multiscrape.util import (create_dict_renderer,
                                                    create_renderer)

    # Arrange
    client = get_async_client(hass, verify_ssl=True)
    params_renderer = lambda vars: {"key": "value", "page": 1}

    wrapper = HttpWrapper(
        config_name="test",
        hass=hass,
        client=client,
        file_manager=None,
        timeout=10,
        params_renderer=params_renderer,
        headers_renderer=create_dict_renderer(hass, None),
        data_renderer=create_renderer(hass, None),
    )

    test_url = "https://example.com/api"
    # respx matches the base URL, params are added by merge_url_with_params
    route = respx.get("https://example.com/api?key=value&page=1").mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    # Act
    response = await wrapper.async_request("test", test_url)

    # Assert
    assert response.text == "OK"
    assert route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_with_data_renderer(hass: HomeAssistant):
    """Test POST request with data renderer."""
    from custom_components.multiscrape.util import create_dict_renderer

    # Arrange
    client = get_async_client(hass, verify_ssl=True)
    data_renderer = lambda vars: "rendered_data"

    wrapper = HttpWrapper(
        config_name="test",
        hass=hass,
        client=client,
        file_manager=None,
        timeout=10,
        method="POST",
        data_renderer=data_renderer,
        params_renderer=create_dict_renderer(hass, None),
        headers_renderer=create_dict_renderer(hass, None),
    )

    test_url = "https://example.com/submit"
    route = respx.post(test_url).mock(return_value=respx.MockResponse(200, text="Submitted"))

    # Act
    response = await wrapper.async_request("test", test_url)

    # Assert
    assert response.text == "Submitted"
    assert route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_with_form_data(http_wrapper_basic):
    """Test POST request with dict payload (form-encoded)."""
    # Arrange
    test_url = "https://example.com/form"
    route = respx.post(test_url).mock(return_value=respx.MockResponse(200, text="Form Submitted"))

    form_data = {"username": "testuser", "password": "testpass"}

    # Act
    response = await http_wrapper_basic.async_request("test", test_url, method="POST", request_data=form_data)

    # Assert
    assert response.text == "Form Submitted"
    assert route.called
    # Verify it was sent as form data
    assert route.calls.last.request.headers.get("content-type") == "application/x-www-form-urlencoded"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_wrapper_with_variables(hass: HomeAssistant):
    """Test that variables are passed to renderers."""
    from custom_components.multiscrape.util import create_renderer

    # Arrange
    client = get_async_client(hass, verify_ssl=True)

    # Create renderers that use variables
    params_renderer = lambda vars: {"user_id": vars.get("user", "unknown")}
    headers_renderer = lambda vars: {"X-Session": vars.get("session", "none")}

    wrapper = HttpWrapper(
        config_name="test",
        hass=hass,
        client=client,
        file_manager=None,
        timeout=10,
        params_renderer=params_renderer,
        headers_renderer=headers_renderer,
        data_renderer=create_renderer(hass, None),
    )

    test_url = "https://example.com/api"
    route = respx.get("https://example.com/api?user_id=john").mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    # Act
    variables = {"user": "john", "session": "sess123"}
    response = await wrapper.async_request("test", test_url, variables=variables)

    # Assert
    assert response.text == "OK"
    assert route.called
    assert route.calls.last.request.headers["X-Session"] == "sess123"
