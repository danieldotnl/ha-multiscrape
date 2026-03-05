"""Tests for the unified HttpSession class."""

from unittest.mock import MagicMock

import httpx
import pytest
import respx
from homeassistant.core import HomeAssistant
from httpx import RequestError, TimeoutException

from custom_components.multiscrape.http_session import (FormAuthConfig,
                                                        HttpConfig,
                                                        HttpSession,
                                                        create_http_session)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def http_config():
    """Create a basic HttpConfig."""
    return HttpConfig(
        verify_ssl=True,
        timeout=10,
        method="GET",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )


@pytest.fixture
def session(hass: HomeAssistant, http_config):
    """Create a basic HttpSession for testing."""
    return HttpSession(
        config_name="test_session",
        hass=hass,
        http_config=http_config,
        file_manager=None,
    )


@pytest.fixture
def mock_file_manager():
    """Create a mock file manager."""
    mock = MagicMock()
    mock.write = MagicMock()
    mock.empty_folder = MagicMock()
    return mock


@pytest.fixture
def session_with_file_manager(hass: HomeAssistant, http_config, mock_file_manager):
    """Create an HttpSession with file logging enabled."""
    return HttpSession(
        config_name="test_session",
        hass=hass,
        http_config=http_config,
        file_manager=mock_file_manager,
    )


FORM_PAGE_HTML = """
<html>
<body>
<form id="login" action="/submit" method="post">
    <input name="username" value="" />
    <input name="password" value="" />
    <input name="csrf_token" value="abc123" />
    <button type="submit">Login</button>
</form>
</body>
</html>
"""

FORM_PAGE_NO_ACTION = """
<html>
<body>
<form id="login" method="post">
    <input name="user" value="" />
    <input name="pass" value="" />
</form>
</body>
</html>
"""


# ============================================================================
# Basic Request Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_basic_get_request(session):
    """Test basic GET request."""
    url = "https://example.com/page"
    respx.get(url).mock(return_value=respx.MockResponse(200, text="Hello"))

    response = await session.async_request("test", url)

    assert response.text == "Hello"
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_post_request_with_dict_data(session):
    """Test POST request with dict data (form-encoded)."""
    url = "https://example.com/api"
    respx.post(url).mock(return_value=respx.MockResponse(201, text="Created"))

    response = await session.async_request(
        "test", url, method="POST", request_data={"key": "value"}
    )

    assert response.status_code == 201


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_post_request_with_string_data(session):
    """Test POST request with string data (raw content)."""
    url = "https://example.com/api"
    respx.post(url).mock(return_value=respx.MockResponse(200, text="OK"))

    response = await session.async_request(
        "test", url, method="POST", request_data="raw body"
    )

    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_method_override(session):
    """Test per-request method overrides default."""
    url = "https://example.com/resource"
    respx.put(url).mock(return_value=respx.MockResponse(200, text="Updated"))

    response = await session.async_request("test", url, method="PUT")

    assert response.text == "Updated"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_default_method_from_config(hass: HomeAssistant):
    """Test that default method comes from config."""
    config = HttpConfig(
        method="POST",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(config_name="test", hass=hass, http_config=config)

    url = "https://example.com/api"
    respx.post(url).mock(return_value=respx.MockResponse(200, text="OK"))

    response = await sess.async_request("test", url)
    assert response.text == "OK"


# ============================================================================
# Cookie Persistence Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_cookies_persist_across_requests(session):
    """Test that cookies from one response are sent in subsequent requests."""
    url1 = "https://example.com/login"
    url2 = "https://example.com/page"

    # First request sets a cookie
    respx.get(url1).mock(
        return_value=respx.MockResponse(
            200,
            text="Logged in",
            headers={"Set-Cookie": "session_id=abc123; Path=/"},
        )
    )
    # Second request should include the cookie automatically
    route = respx.get(url2).mock(return_value=respx.MockResponse(200, text="Content"))

    await session.async_request("login", url1)
    await session.async_request("page", url2)

    # Verify cookie was sent in second request
    assert route.called
    request = route.calls.last.request
    assert "session_id=abc123" in request.headers.get("cookie", "")


# ============================================================================
# Authentication Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_basic_auth(hass: HomeAssistant):
    """Test basic HTTP authentication."""
    config = HttpConfig(
        username="user",
        password="pass",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(config_name="test", hass=hass, http_config=config)

    url = "https://example.com/protected"
    route = respx.get(url).mock(return_value=respx.MockResponse(200, text="OK"))

    await sess.async_request("test", url)
    assert route.called
    request = route.calls.last.request
    assert "authorization" in request.headers


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
async def test_digest_auth_setup(hass: HomeAssistant):
    """Test digest auth is configured correctly."""
    from homeassistant.const import HTTP_DIGEST_AUTHENTICATION

    config = HttpConfig(
        username="user",
        password="pass",
        auth_type=HTTP_DIGEST_AUTHENTICATION,
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(config_name="test", hass=hass, http_config=config)

    assert isinstance(sess._auth, httpx.DigestAuth)


# ============================================================================
# Header/Param Renderer Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_headers_from_renderer(hass: HomeAssistant):
    """Test that headers are rendered from the config renderer."""
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {
            "X-Custom": "test-value",
            "Authorization": "Bearer token123",
        },
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(config_name="test", hass=hass, http_config=config)

    url = "https://example.com/api"
    route = respx.get(url).mock(return_value=respx.MockResponse(200, text="OK"))

    await sess.async_request("test", url)

    request = route.calls.last.request
    assert request.headers["x-custom"] == "test-value"
    assert request.headers["authorization"] == "Bearer token123"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_params_merged_into_url(hass: HomeAssistant):
    """Test that params from renderer are merged into the URL."""
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {"key": "value"},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(config_name="test", hass=hass, http_config=config)

    url = "https://example.com/api"
    route = respx.get(url=__import__("httpx").URL("https://example.com/api?key=value")).mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    await sess.async_request("test", url)
    assert route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_variables_passed_to_renderers(hass: HomeAssistant):
    """Test that variables dict is passed to renderers."""
    received_vars = {}

    def capture_headers(variables={}, parse_result=None):
        received_vars.update(variables)
        return {}

    config = HttpConfig(
        headers_renderer=capture_headers,
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(config_name="test", hass=hass, http_config=config)

    url = "https://example.com/api"
    respx.get(url).mock(return_value=respx.MockResponse(200, text="OK"))

    await sess.async_request("test", url, variables={"token": "xyz"})

    assert received_vars == {"token": "xyz"}


# ============================================================================
# Form Authentication Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_auth_with_selector(hass: HomeAssistant):
    """Test form authentication with CSS selector."""
    form_config = FormAuthConfig(
        resource="https://example.com/login",
        select="#login",
        input_values={"username": "admin", "password": "secret"},
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    # Mock form page fetch
    respx.get("https://example.com/login").mock(
        return_value=respx.MockResponse(200, text=FORM_PAGE_HTML)
    )
    # Mock form submission
    submit_route = respx.post("https://example.com/submit").mock(
        return_value=respx.MockResponse(200, text="Welcome!")
    )

    result = await sess.ensure_authenticated("https://example.com/main")

    # Form has its own resource, so result should be None
    assert result is None
    assert submit_route.called
    # Verify form fields were submitted (merged: scraped + config input)
    request = submit_route.calls.last.request
    body = request.content.decode()
    assert "username=admin" in body
    assert "password=secret" in body
    assert "csrf_token=abc123" in body


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_auth_without_selector(hass: HomeAssistant):
    """Test form auth without selector (all input from config)."""
    form_config = FormAuthConfig(
        input_values={"user": "admin", "pass": "secret"},
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    # No form page fetch should happen; POST directly to main resource
    submit_route = respx.post("https://example.com/main").mock(
        return_value=respx.MockResponse(200, text="Logged in content")
    )

    result = await sess.ensure_authenticated("https://example.com/main")

    # No form resource set, so returns response text
    assert result == "Logged in content"
    assert submit_route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_auth_uses_main_resource_returns_text(hass: HomeAssistant):
    """Test that when form has no own resource, response text is returned."""
    form_config = FormAuthConfig(
        resource=None,
        select="#login",
        input_values={"username": "admin"},
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    # Form page is fetched from main resource
    respx.get("https://example.com/main").mock(
        return_value=respx.MockResponse(200, text=FORM_PAGE_HTML)
    )
    respx.post("https://example.com/submit").mock(
        return_value=respx.MockResponse(200, text="Scraped content here")
    )

    result = await sess.ensure_authenticated("https://example.com/main")

    # No form resource → returns response text
    assert result == "Scraped content here"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_auth_submit_once(hass: HomeAssistant):
    """Test submit_once prevents subsequent submissions."""
    form_config = FormAuthConfig(
        input_values={"user": "admin"},
        submit_once=True,
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    respx.post("https://example.com/main").mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    # First call submits
    await sess.ensure_authenticated("https://example.com/main")
    assert not sess._should_submit

    # Second call skips
    result = await sess.ensure_authenticated("https://example.com/main")
    assert result is None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_auth_resubmit_on_error(hass: HomeAssistant):
    """Test resubmit_on_error resets should_submit after exception notification."""
    form_config = FormAuthConfig(
        input_values={"user": "admin"},
        submit_once=True,
        resubmit_on_error=True,
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    respx.post("https://example.com/main").mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    # Submit once
    await sess.ensure_authenticated("https://example.com/main")
    assert not sess._should_submit

    # Notify scrape exception
    sess.notify_scrape_exception()
    assert sess._should_submit

    # Now it should submit again
    await sess.ensure_authenticated("https://example.com/main")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_auth_input_filter(hass: HomeAssistant):
    """Test input_filter removes specified fields from form."""
    form_config = FormAuthConfig(
        resource="https://example.com/login",
        select="#login",
        input_values={"username": "admin", "password": "secret"},
        input_filter=["csrf_token"],
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    respx.get("https://example.com/login").mock(
        return_value=respx.MockResponse(200, text=FORM_PAGE_HTML)
    )
    submit_route = respx.post("https://example.com/submit").mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    await sess.ensure_authenticated("https://example.com/main")

    body = submit_route.calls.last.request.content.decode()
    assert "csrf_token" not in body
    assert "username=admin" in body


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_action_url_resolution(hass: HomeAssistant):
    """Test _determine_submit_resource with various URL combinations."""
    form_config = FormAuthConfig(
        resource="https://example.com/auth/login",
        select="#login",
        input_values={"user": "admin"},
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    # action + form_resource → urljoin(form_resource, action)
    result = sess._determine_submit_resource("/do_login", "https://main.com/page")
    assert result == "https://example.com/do_login"


@pytest.mark.unit
def test_determine_submit_resource_action_no_form_resource(hass: HomeAssistant):
    """Test URL resolution: action + no form_resource → urljoin(main, action)."""
    form_config = FormAuthConfig(
        resource=None,
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    result = sess._determine_submit_resource("/login", "https://main.com/page")
    assert result == "https://main.com/login"


@pytest.mark.unit
def test_determine_submit_resource_no_action_with_form_resource(hass: HomeAssistant):
    """Test URL resolution: no action + form_resource → form_resource."""
    form_config = FormAuthConfig(
        resource="https://example.com/auth/login",
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    result = sess._determine_submit_resource(None, "https://main.com/page")
    assert result == "https://example.com/auth/login"


@pytest.mark.unit
def test_determine_submit_resource_no_action_no_form_resource(hass: HomeAssistant):
    """Test URL resolution: no action + no form_resource → main_resource."""
    form_config = FormAuthConfig(
        resource=None,
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    result = sess._determine_submit_resource(None, "https://main.com/page")
    assert result == "https://main.com/page"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_method_from_html(hass: HomeAssistant):
    """Test that form method is extracted from HTML form tag."""
    form_html = """
    <html><body>
    <form id="login" action="/submit" method="PUT">
        <input name="data" value="test" />
    </form>
    </body></html>
    """
    form_config = FormAuthConfig(
        resource="https://example.com/login",
        select="#login",
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )

    respx.get("https://example.com/login").mock(
        return_value=respx.MockResponse(200, text=form_html)
    )
    submit_route = respx.put("https://example.com/submit").mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    await sess.ensure_authenticated("https://example.com/main")
    assert submit_route.called


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_timeout_error(session):
    """Test timeout exception is raised."""
    url = "https://example.com/slow"
    respx.get(url).mock(side_effect=TimeoutException("Timed out"))

    with pytest.raises(TimeoutException):
        await session.async_request("test", url)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_request_error(session):
    """Test request error is raised."""
    url = "https://example.com/broken"
    respx.get(url).mock(side_effect=RequestError("Connection failed"))

    with pytest.raises(RequestError):
        await session.async_request("test", url)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_http_error_status(session):
    """Test that 4xx/5xx status codes raise."""
    url = "https://example.com/notfound"
    respx.get(url).mock(return_value=respx.MockResponse(404, text="Not Found"))

    with pytest.raises(httpx.HTTPStatusError):
        await session.async_request("test", url)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_server_error_status(session):
    """Test that 500 status codes raise."""
    url = "https://example.com/error"
    respx.get(url).mock(return_value=respx.MockResponse(500, text="Internal Error"))

    with pytest.raises(httpx.HTTPStatusError):
        await session.async_request("test", url)


# ============================================================================
# File Logging Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_file_logging_on_success(session_with_file_manager, mock_file_manager):
    """Test that request/response are logged to files."""
    url = "https://example.com/page"
    respx.get(url).mock(return_value=respx.MockResponse(200, text="Content"))

    await session_with_file_manager.async_request("test", url)

    # Verify file manager write was called for request and response
    assert mock_file_manager.write.call_count >= 2


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_file_logging_on_error(session_with_file_manager, mock_file_manager):
    """Test that error responses are logged to files."""
    url = "https://example.com/error"
    respx.get(url).mock(return_value=respx.MockResponse(500, text="Error"))

    with pytest.raises(httpx.HTTPStatusError):
        await session_with_file_manager.async_request("test", url)

    # Should have logged both request and error response
    assert mock_file_manager.write.call_count >= 2


# ============================================================================
# Session Lifecycle Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_async_close(session):
    """Test that async_close closes the client."""
    await session.async_close()
    assert session._client.is_closed


@pytest.mark.unit
def test_no_form_auth_returns_empty_variables(session):
    """Test form_variables is empty when no form auth configured."""
    assert session.form_variables == {}


@pytest.mark.unit
def test_notify_scrape_exception_without_form(session):
    """Test notify_scrape_exception is a no-op without form auth."""
    # Should not raise
    session.notify_scrape_exception()


@pytest.mark.unit
def test_notify_scrape_exception_resubmit_disabled(hass: HomeAssistant):
    """Test notify_scrape_exception does nothing when resubmit_on_error is False."""
    form_config = FormAuthConfig(
        resubmit_on_error=False,
        parser="html.parser",
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    config = HttpConfig(
        headers_renderer=lambda variables={}, parse_result=None: {},
        params_renderer=lambda variables={}, parse_result=None: {},
        data_renderer=lambda variables={}, parse_result=None: None,
    )
    sess = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        form_auth_config=form_config,
    )
    sess._should_submit = False
    sess.notify_scrape_exception()
    assert not sess._should_submit


# ============================================================================
# No Form Auth Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_ensure_authenticated_no_form(session):
    """Test ensure_authenticated returns None when no form auth."""
    result = await session.ensure_authenticated("https://example.com/page")
    assert result is None


# ============================================================================
# Factory Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_create_http_session_basic(hass: HomeAssistant):
    """Test factory creates session from basic config."""
    conf = {
        "resource": "https://example.com",
        "method": "get",
        "verify_ssl": True,
        "timeout": 15,
    }
    session = create_http_session("test", conf, hass, None)

    assert session._http_config.verify_ssl is True
    assert session._http_config.timeout == 15
    assert session._form_auth_config is None

    await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_create_http_session_with_form(hass: HomeAssistant):
    """Test factory creates session with form auth config."""
    conf = {
        "resource": "https://example.com",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://example.com/login",
            "select": "#login",
            "input": {"user": "admin"},
            "input_filter": [],
            "submit_once": True,
            "resubmit_on_error": False,
            "variables": [],
            "method": "post",
            "verify_ssl": True,
            "timeout": 10,
        },
    }
    session = create_http_session("test", conf, hass, None)

    assert session._form_auth_config is not None
    assert session._form_auth_config.resource == "https://example.com/login"
    assert session._form_auth_config.select == "#login"
    assert session._form_auth_config.submit_once is True
    assert session._form_auth_config.resubmit_on_error is False

    await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_create_http_session_with_auth(hass: HomeAssistant):
    """Test factory creates session with HTTP auth."""
    conf = {
        "resource": "https://example.com",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "username": "user",
        "password": "pass",
    }
    session = create_http_session("test", conf, hass, None)

    assert session._auth is not None
    assert session._auth == ("user", "pass")

    await session.async_close()
