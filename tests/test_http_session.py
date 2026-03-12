"""Tests for the unified HttpSession class."""

from unittest.mock import MagicMock

import httpx
import pytest
import respx
from homeassistant.core import HomeAssistant
from httpx import RequestError, TimeoutException

from custom_components.multiscrape.form_auth import (FormAuthConfig,
                                                     FormAuthenticator)
from custom_components.multiscrape.http_session import (HttpConfig,
                                                        HttpSession,
                                                        create_http_session)
from custom_components.multiscrape.scrape_context import ScrapeContext

# ============================================================================
# Test helpers
# ============================================================================

_NOOP_HEADERS = lambda variables={}, parse_result=None: {}
_NOOP_PARAMS = lambda variables={}, parse_result=None: {}
_NOOP_DATA = lambda variables={}, parse_result=None: None


def make_http_config(**overrides):
    """Create an HttpConfig with sensible defaults for testing."""
    defaults = {
        "headers_renderer": _NOOP_HEADERS,
        "params_renderer": _NOOP_PARAMS,
        "data_renderer": _NOOP_DATA,
    }
    return HttpConfig(**{**defaults, **overrides})


def make_form_config(**overrides):
    """Create a FormAuthConfig with sensible defaults for testing."""
    defaults = {
        "parser": "html.parser",
        "headers_renderer": _NOOP_HEADERS,
        "params_renderer": _NOOP_PARAMS,
        "data_renderer": _NOOP_DATA,
    }
    return FormAuthConfig(**{**defaults, **overrides})


def make_form_session(hass, form_config, http_config=None, file_manager=None):
    """Create an HttpSession with a FormAuthenticator wired up for testing."""
    config = http_config or make_http_config()
    session = HttpSession(
        config_name="test",
        hass=hass,
        http_config=config,
        file_manager=file_manager,
    )
    authenticator = FormAuthenticator(
        config_name="test",
        config=form_config,
        execute_request=session._execute_request,
        file_log=session._async_file_log if file_manager else None,
    )
    session._form_authenticator = authenticator
    return session


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def http_config():
    """Create a basic HttpConfig."""
    return make_http_config(verify_ssl=True, timeout=10, method="GET")


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
    config = make_http_config(method="POST")
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
    config = make_http_config(username="user", password="pass")
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

    config = make_http_config(
        username="user",
        password="pass",
        auth_type=HTTP_DIGEST_AUTHENTICATION,
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
    config = make_http_config(
        headers_renderer=lambda variables={}, parse_result=None: {
            "X-Custom": "test-value",
            "Authorization": "Bearer token123",
        },
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
    config = make_http_config(
        params_renderer=lambda variables={}, parse_result=None: {"key": "value"},
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

    config = make_http_config(headers_renderer=capture_headers)
    sess = HttpSession(config_name="test", hass=hass, http_config=config)

    url = "https://example.com/api"
    respx.get(url).mock(return_value=respx.MockResponse(200, text="OK"))

    await sess.async_request("test", url, scrape_context=ScrapeContext(form_variables={"token": "xyz"}))

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
    form_config = make_form_config(
        resource="https://example.com/login",
        select="#login",
        input_values={"username": "admin", "password": "secret"},
    )
    sess = make_form_session(hass, form_config)

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
    form_config = make_form_config(
        input_values={"user": "admin", "pass": "secret"},
    )
    sess = make_form_session(hass, form_config)

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
    form_config = make_form_config(
        resource=None,
        select="#login",
        input_values={"username": "admin"},
    )
    sess = make_form_session(hass, form_config)

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
    form_config = make_form_config(
        input_values={"user": "admin"},
        submit_once=True,
    )
    sess = make_form_session(hass, form_config)

    respx.post("https://example.com/main").mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    # First call submits
    await sess.ensure_authenticated("https://example.com/main")
    assert not sess._form_authenticator._should_submit

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
    form_config = make_form_config(
        input_values={"user": "admin"},
        submit_once=True,
        resubmit_on_error=True,
    )
    sess = make_form_session(hass, form_config)

    respx.post("https://example.com/main").mock(
        return_value=respx.MockResponse(200, text="OK")
    )

    # Submit once
    await sess.ensure_authenticated("https://example.com/main")
    assert not sess._form_authenticator._should_submit

    # Notify scrape exception
    sess.notify_scrape_exception()
    assert sess._form_authenticator._should_submit

    # Now it should submit again
    await sess.ensure_authenticated("https://example.com/main")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.http
@pytest.mark.timeout(10)
@respx.mock
async def test_form_auth_input_filter(hass: HomeAssistant):
    """Test input_filter removes specified fields from form."""
    form_config = make_form_config(
        resource="https://example.com/login",
        select="#login",
        input_values={"username": "admin", "password": "secret"},
        input_filter=["csrf_token"],
    )
    sess = make_form_session(hass, form_config)

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
    form_config = make_form_config(
        resource="https://example.com/auth/login",
        select="#login",
        input_values={"user": "admin"},
    )
    auth = FormAuthenticator(
        config_name="test",
        config=form_config,
        execute_request=lambda **kwargs: None,
    )

    # action + form_resource → urljoin(form_resource, action)
    result = auth._determine_submit_resource("/do_login", "https://main.com/page")
    assert result == "https://example.com/do_login"


@pytest.mark.unit
def test_determine_submit_resource_action_no_form_resource(hass: HomeAssistant):
    """Test URL resolution: action + no form_resource → urljoin(main, action)."""
    form_config = make_form_config(resource=None)
    auth = FormAuthenticator(
        config_name="test",
        config=form_config,
        execute_request=lambda **kwargs: None,
    )

    result = auth._determine_submit_resource("/login", "https://main.com/page")
    assert result == "https://main.com/login"


@pytest.mark.unit
def test_determine_submit_resource_no_action_with_form_resource(hass: HomeAssistant):
    """Test URL resolution: no action + form_resource → form_resource."""
    form_config = make_form_config(resource="https://example.com/auth/login")
    auth = FormAuthenticator(
        config_name="test",
        config=form_config,
        execute_request=lambda **kwargs: None,
    )

    result = auth._determine_submit_resource(None, "https://main.com/page")
    assert result == "https://example.com/auth/login"


@pytest.mark.unit
def test_determine_submit_resource_no_action_no_form_resource(hass: HomeAssistant):
    """Test URL resolution: no action + no form_resource → main_resource."""
    form_config = make_form_config(resource=None)
    auth = FormAuthenticator(
        config_name="test",
        config=form_config,
        execute_request=lambda **kwargs: None,
    )

    result = auth._determine_submit_resource(None, "https://main.com/page")
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
    form_config = make_form_config(
        resource="https://example.com/login",
        select="#login",
    )
    sess = make_form_session(hass, form_config)

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
    form_config = make_form_config(resubmit_on_error=False)
    sess = make_form_session(hass, form_config)
    sess._form_authenticator._should_submit = False
    sess.notify_scrape_exception()
    assert not sess._form_authenticator._should_submit


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
    assert session._form_authenticator is None

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

    assert session._form_authenticator is not None
    assert session._form_authenticator._config.resource == "https://example.com/login"
    assert session._form_authenticator._config.select == "#login"
    assert session._form_authenticator._config.submit_once is True
    assert session._form_authenticator._config.resubmit_on_error is False

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


# ============================================================================
# End-to-End Integration Tests
# ============================================================================

LOGIN_PAGE_HTML = """
<html>
<body>
<form id="loginform" action="/auth/submit" method="post">
    <input name="username" value="" />
    <input name="password" value="" />
    <input name="csrf" value="tok_abc" />
    <button type="submit">Login</button>
</form>
</body>
</html>
"""

TARGET_PAGE_HTML = """
<html>
<body>
<div class="temperature">21.5</div>
<div class="humidity">58</div>
</body>
</html>
"""


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_login_then_scrape_separate_resource(hass: HomeAssistant):
    """End-to-end: form login on separate URL, then scrape target page.

    Flow: GET /login -> parse form -> POST /auth/submit -> GET /data -> scrape
    Cookies from login must persist to the data page request.
    """
    from custom_components.multiscrape.coordinator import \
        create_content_request_manager

    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": False,
            "resubmit_on_error": True,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("e2e_test", conf, hass, None)

    try:
        # Mock login page
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(
                200,
                text=LOGIN_PAGE_HTML,
                headers={"Set-Cookie": "session_id=sess123; Path=/"},
            )
        )
        # Mock form submission — returns a redirect-style page (not the target)
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(
                200,
                text="<html><body>Login successful</body></html>",
                headers={"Set-Cookie": "auth_token=xyz; Path=/"},
            )
        )
        # Mock target data page
        data_route = respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        request_manager = create_content_request_manager(
            "e2e_test", conf, hass, session
        )
        content = await request_manager.get_content()

        # Should have fetched the target page (form has own resource → returns None)
        assert data_route.called
        assert "21.5" in content
        assert "humidity" in content

        # Verify cookies were sent to the data page
        data_request = data_route.calls.last.request
        cookie_header = data_request.headers.get("cookie", "")
        assert "session_id=sess123" in cookie_header
        assert "auth_token=xyz" in cookie_header
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_login_same_resource(hass: HomeAssistant):
    """End-to-end: form login on same URL as target — form response IS the content.

    When form_submit has no separate resource, the form response text is used
    directly as the scraped content (no second GET needed).
    """
    from custom_components.multiscrape.coordinator import \
        create_content_request_manager

    conf = {
        "resource": "https://site.com/dashboard",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": False,
            "resubmit_on_error": True,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("e2e_test", conf, hass, None)

    try:
        # Form page is the main resource itself
        respx.get("https://site.com/dashboard").mock(
            return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
        )
        # Form submits to /auth/submit (from form action)
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        request_manager = create_content_request_manager(
            "e2e_test", conf, hass, session
        )
        content = await request_manager.get_content()

        # Form response is used directly as content (no separate GET for target)
        assert "21.5" in content
        assert "humidity" in content
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_submit_once_skips_on_second_call(hass: HomeAssistant):
    """End-to-end: submit_once=True skips form on second coordinator update."""
    from custom_components.multiscrape.coordinator import \
        create_content_request_manager

    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": True,
            "resubmit_on_error": True,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("e2e_test", conf, hass, None)

    try:
        login_route = respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
        )
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(200, text="OK")
        )
        respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        request_manager = create_content_request_manager(
            "e2e_test", conf, hass, session
        )

        # First call — form login happens
        await request_manager.get_content()
        assert login_route.call_count == 1

        # Second call — form login skipped (submit_once=True)
        await request_manager.get_content()
        assert login_route.call_count == 1  # Still 1, not 2
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_resubmit_on_error(hass: HomeAssistant):
    """End-to-end: resubmit_on_error re-submits form after scrape exception."""
    from custom_components.multiscrape.coordinator import \
        create_content_request_manager

    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": True,
            "resubmit_on_error": True,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("e2e_test", conf, hass, None)

    try:
        login_route = respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
        )
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(200, text="OK")
        )
        respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        request_manager = create_content_request_manager(
            "e2e_test", conf, hass, session
        )

        # First call — form login
        await request_manager.get_content()
        assert login_route.call_count == 1

        # Simulate scrape exception notification
        request_manager.notify_scrape_exception()

        # Third call — form re-submits after error
        await request_manager.get_content()
        assert login_route.call_count == 2
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_no_form_just_scrape(hass: HomeAssistant):
    """End-to-end: simple scrape without form authentication."""
    from custom_components.multiscrape.coordinator import \
        create_content_request_manager

    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
    }

    session = create_http_session("e2e_test", conf, hass, None)

    try:
        respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        request_manager = create_content_request_manager(
            "e2e_test", conf, hass, session
        )
        content = await request_manager.get_content()

        assert "21.5" in content
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_auth_error_falls_back_to_page_fetch(hass: HomeAssistant):
    """End-to-end: when form auth fails, ContentRequestManager still tries to fetch the page."""
    from custom_components.multiscrape.coordinator import \
        create_content_request_manager

    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": False,
            "resubmit_on_error": True,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("e2e_test", conf, hass, None)

    try:
        # Form page returns garbage (no form element) — will raise ValueError
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(200, text="<html><body>No form here</body></html>")
        )
        # But the target page is available
        data_route = respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        request_manager = create_content_request_manager(
            "e2e_test", conf, hass, session
        )
        content = await request_manager.get_content()

        # Should fall back to fetching the target page directly
        assert data_route.called
        assert "21.5" in content
    finally:
        await session.async_close()


# ============================================================================
# End-to-End Cookie Persistence Tests
# ============================================================================

LOGIN_PAGE_WITH_TOKEN_HTML = """
<html>
<body>
<form id="loginform" action="/auth/submit" method="post">
    <input name="username" value="" />
    <input name="password" value="" />
    <input name="csrf" value="tok_abc" />
    <button type="submit">Login</button>
</form>
<div class="api-token">scraped_token_123</div>
<div class="session-key">session_key_abc</div>
</body>
</html>
"""


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_cookies_from_form_page_get_persist_to_submit(hass: HomeAssistant):
    """End-to-end: cookies set during form page GET persist to form POST.

    When fetching the login page, the server sets a cookie. That cookie
    must be included in the subsequent form POST request.
    """
    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": False,
            "resubmit_on_error": False,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("cookie_test", conf, hass, None)

    try:
        # Form page sets a tracking cookie
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(
                200,
                text=LOGIN_PAGE_HTML,
                headers={"Set-Cookie": "tracking_id=track_001; Path=/"},
            )
        )
        # Form submission — verify the tracking cookie arrived
        submit_route = respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(200, text="OK")
        )
        respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        from custom_components.multiscrape.coordinator import \
            create_content_request_manager

        request_manager = create_content_request_manager(
            "cookie_test", conf, hass, session
        )
        await request_manager.get_content()

        # The form submit POST should carry the cookie from the GET
        submit_request = submit_route.calls.last.request
        cookie_header = submit_request.headers.get("cookie", "")
        assert "tracking_id=track_001" in cookie_header
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_cookies_accumulate_across_all_steps(hass: HomeAssistant):
    """End-to-end: cookies accumulate from GET → POST → data page.

    Three cookies set at different stages must all arrive at the final data page request.
    """
    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": False,
            "resubmit_on_error": False,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("cookie_accum_test", conf, hass, None)

    try:
        # Step 1: GET login page sets cookie_a
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(
                200,
                text=LOGIN_PAGE_HTML,
                headers={"Set-Cookie": "cookie_a=aaa; Path=/"},
            )
        )
        # Step 2: POST form submission sets cookie_b
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(
                200,
                text="OK",
                headers={"Set-Cookie": "cookie_b=bbb; Path=/"},
            )
        )
        # Step 3: GET data page — should carry both cookie_a and cookie_b
        data_route = respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        from custom_components.multiscrape.coordinator import \
            create_content_request_manager

        request_manager = create_content_request_manager(
            "cookie_accum_test", conf, hass, session
        )
        await request_manager.get_content()

        data_request = data_route.calls.last.request
        cookie_header = data_request.headers.get("cookie", "")
        assert "cookie_a=aaa" in cookie_header
        assert "cookie_b=bbb" in cookie_header
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_cookies_persist_across_multiple_scrape_cycles(hass: HomeAssistant):
    """End-to-end: cookies from auth persist across multiple get_content calls.

    With submit_once=True, cookies established during the first auth
    must still be present on subsequent data page requests.
    """
    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": True,
            "resubmit_on_error": False,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("cookie_persist_test", conf, hass, None)

    try:
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(
                200,
                text=LOGIN_PAGE_HTML,
                headers={"Set-Cookie": "session_id=sess999; Path=/"},
            )
        )
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(
                200,
                text="OK",
                headers={"Set-Cookie": "auth=tok999; Path=/"},
            )
        )
        data_route = respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        from custom_components.multiscrape.coordinator import \
            create_content_request_manager

        request_manager = create_content_request_manager(
            "cookie_persist_test", conf, hass, session
        )

        # First cycle — auth + data
        await request_manager.get_content()
        first_cookie = data_route.calls.last.request.headers.get("cookie", "")
        assert "session_id=sess999" in first_cookie
        assert "auth=tok999" in first_cookie

        # Second cycle — submit_once means no re-auth, but cookies persist
        await request_manager.get_content()
        second_cookie = data_route.calls.last.request.headers.get("cookie", "")
        assert "session_id=sess999" in second_cookie
        assert "auth=tok999" in second_cookie
    finally:
        await session.async_close()


# ============================================================================
# End-to-End Form Variables Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_variables_scraped_from_response(hass: HomeAssistant):
    """End-to-end: form variables are scraped from the form response.

    Configures variables with CSS selectors that extract values from the
    form submission response. Verifies session.form_variables contains
    the scraped data.
    """
    from homeassistant.helpers.template import Template

    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": False,
            "resubmit_on_error": False,
            "variables": [
                {
                    "name": "api_token",
                    "select": Template(".api-token", hass),
                    "extract": "text",
                },
                {
                    "name": "session_key",
                    "select": Template(".session-key", hass),
                    "extract": "text",
                },
            ],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
            "parser": "html.parser",
            "separator": ",",
        },
    }

    session = create_http_session("var_test", conf, hass, None)

    try:
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(200, text=LOGIN_PAGE_WITH_TOKEN_HTML)
        )
        # Form submission response contains the values to scrape
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(
                200,
                text=LOGIN_PAGE_WITH_TOKEN_HTML,
            )
        )
        respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        from custom_components.multiscrape.coordinator import \
            create_content_request_manager

        request_manager = create_content_request_manager(
            "var_test", conf, hass, session
        )
        await request_manager.get_content()

        # Verify variables were scraped from form response
        assert session.form_variables.get("api_token") == "scraped_token_123"
        assert session.form_variables.get("session_key") == "session_key_abc"

        # Verify form_variables is also accessible via request_manager
        assert request_manager.form_variables.get("api_token") == "scraped_token_123"
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_variables_passed_to_page_request_headers(hass: HomeAssistant):
    """End-to-end: scraped form variables are used in subsequent request headers.

    Configures headers with a template that references form variables.
    Verifies the data page request includes the rendered header value.
    """
    from homeassistant.helpers.template import Template

    # We need a headers renderer that uses the variables
    def headers_renderer(variables={}, parse_result=None):
        token = variables.get("api_token", "")
        return {"Authorization": f"Bearer {token}"}

    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": False,
            "resubmit_on_error": False,
            "variables": [
                {
                    "name": "api_token",
                    "select": Template(".api-token", hass),
                    "extract": "text",
                },
            ],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
            "parser": "html.parser",
            "separator": ",",
        },
    }

    session = create_http_session("var_header_test", conf, hass, None)
    # Override the headers renderer to use variables
    session._http_config.headers_renderer = headers_renderer

    try:
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(200, text=LOGIN_PAGE_WITH_TOKEN_HTML)
        )
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(200, text=LOGIN_PAGE_WITH_TOKEN_HTML)
        )
        data_route = respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        from custom_components.multiscrape.coordinator import \
            create_content_request_manager

        request_manager = create_content_request_manager(
            "var_header_test", conf, hass, session
        )
        content = await request_manager.get_content()

        # Verify the data page request included the rendered Authorization header
        data_request = data_route.calls.last.request
        assert data_request.headers.get("authorization") == "Bearer scraped_token_123"

        # Also verify the content was returned correctly
        assert "21.5" in content
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_variables_updated_on_resubmit(hass: HomeAssistant):
    """End-to-end: form variables are refreshed when form is resubmitted.

    After a scrape exception triggers resubmit, the form response may
    contain new variable values (e.g., rotated token). Verify the new
    values replace the old ones.
    """
    from homeassistant.helpers.template import Template

    FORM_RESPONSE_V1 = """
    <html><body>
    <div class="api-token">token_v1</div>
    </body></html>
    """
    FORM_RESPONSE_V2 = """
    <html><body>
    <div class="api-token">token_v2</div>
    </body></html>
    """

    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": True,
            "resubmit_on_error": True,
            "variables": [
                {
                    "name": "api_token",
                    "select": Template(".api-token", hass),
                    "extract": "text",
                },
            ],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
            "parser": "html.parser",
            "separator": ",",
        },
    }

    session = create_http_session("var_refresh_test", conf, hass, None)

    try:
        # First auth cycle returns token_v1
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
        )
        submit_route = respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(200, text=FORM_RESPONSE_V1)
        )
        respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        from custom_components.multiscrape.coordinator import \
            create_content_request_manager

        request_manager = create_content_request_manager(
            "var_refresh_test", conf, hass, session
        )

        # First cycle
        await request_manager.get_content()
        assert session.form_variables["api_token"] == "token_v1"

        # Trigger resubmit
        request_manager.notify_scrape_exception()

        # Second auth returns token_v2
        submit_route.mock(
            return_value=respx.MockResponse(200, text=FORM_RESPONSE_V2)
        )

        await request_manager.get_content()
        assert session.form_variables["api_token"] == "token_v2"
    finally:
        await session.async_close()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@respx.mock
async def test_e2e_form_variables_empty_when_no_variables_configured(
    hass: HomeAssistant,
):
    """End-to-end: form_variables remains empty when no variables configured."""
    conf = {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": {
            "resource": "https://site.com/login",
            "select": "#loginform",
            "input": {"username": "admin", "password": "secret"},
            "input_filter": [],
            "submit_once": False,
            "resubmit_on_error": False,
            "variables": [],
            "method": "get",
            "verify_ssl": True,
            "timeout": 10,
        },
    }

    session = create_http_session("no_var_test", conf, hass, None)

    try:
        respx.get("https://site.com/login").mock(
            return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
        )
        respx.post("https://site.com/auth/submit").mock(
            return_value=respx.MockResponse(200, text="OK")
        )
        respx.get("https://site.com/data").mock(
            return_value=respx.MockResponse(200, text=TARGET_PAGE_HTML)
        )

        from custom_components.multiscrape.coordinator import \
            create_content_request_manager

        request_manager = create_content_request_manager(
            "no_var_test", conf, hass, session
        )
        await request_manager.get_content()

        assert session.form_variables == {}
        assert request_manager.form_variables == {}
    finally:
        await session.async_close()
