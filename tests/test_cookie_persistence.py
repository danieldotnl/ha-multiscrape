"""Tests for cookie persistence across HTTP requests.

These tests verify that the httpx.AsyncClient cookie jar correctly
manages cookies across different stages of the scraping workflow:
- Cookies set by initial requests persist to subsequent requests
- Multiple cookies from different domains/paths are handled
- Cookie updates (server sends new value for existing cookie) work
- Cookies persist across multiple scraping cycles
- Cookies from form auth flow persist to data requests
- Cookie overwrite behavior (server replaces cookies)
"""

import httpx
import pytest
import respx
from homeassistant.core import HomeAssistant

from custom_components.multiscrape.coordinator import \
    create_content_request_manager
from custom_components.multiscrape.http_session import (HttpConfig,
                                                        HttpSession,
                                                        create_http_session)

# ============================================================================
# Test helpers
# ============================================================================

_NOOP_HEADERS = lambda variables={}, parse_result=None: {}
_NOOP_PARAMS = lambda variables={}, parse_result=None: {}
_NOOP_DATA = lambda variables={}, parse_result=None: None

LOGIN_PAGE_HTML = """
<html><body>
<form id="loginform" action="/auth/submit" method="post">
    <input name="username" value="" />
    <input name="password" value="" />
    <input name="csrf" value="tok_abc" />
    <button type="submit">Login</button>
</form>
</body></html>
"""

DATA_PAGE_HTML = """
<html><body>
<div class="temperature">21.5</div>
<div class="humidity">58</div>
</body></html>
"""


def make_http_config(**overrides):
    """Create an HttpConfig with sensible defaults for testing."""
    defaults = {
        "headers_renderer": _NOOP_HEADERS,
        "params_renderer": _NOOP_PARAMS,
        "data_renderer": _NOOP_DATA,
    }
    return HttpConfig(**{**defaults, **overrides})


def make_form_conf(**overrides):
    """Create a full config dict with form_submit for create_http_session."""
    defaults = {
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
    if overrides:
        for key, value in overrides.items():
            if key == "form_submit" and isinstance(value, dict):
                defaults["form_submit"].update(value)
            else:
                defaults[key] = value
    return defaults


# ============================================================================
# Basic Cookie Persistence Tests
# ============================================================================


class TestBasicCookiePersistence:
    """Test that cookies from HTTP responses persist across requests."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_single_cookie_persists_across_requests(self, hass: HomeAssistant):
        """Test that a single Set-Cookie from one response is sent in the next request."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            url1 = "https://example.com/page1"
            url2 = "https://example.com/page2"

            respx.get(url1).mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "session_id=abc123; Path=/"},
                )
            )
            route2 = respx.get(url2).mock(
                return_value=respx.MockResponse(200, text="Content")
            )

            await session.async_request("first", url1)
            await session.async_request("second", url2)

            request = route2.calls.last.request
            assert "session_id=abc123" in request.headers.get("cookie", "")
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_multiple_cookies_accumulate(self, hass: HomeAssistant):
        """Test that cookies from multiple responses accumulate in the cookie jar."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            url1 = "https://example.com/login"
            url2 = "https://example.com/dashboard"
            url3 = "https://example.com/api"

            respx.get(url1).mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "cookie_a=value_a; Path=/"},
                )
            )
            respx.get(url2).mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "cookie_b=value_b; Path=/"},
                )
            )
            route3 = respx.get(url3).mock(
                return_value=respx.MockResponse(200, text="Data")
            )

            await session.async_request("login", url1)
            await session.async_request("dashboard", url2)
            await session.async_request("api", url3)

            cookies = route3.calls.last.request.headers.get("cookie", "")
            assert "cookie_a=value_a" in cookies
            assert "cookie_b=value_b" in cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookie_value_updated_by_server(self, hass: HomeAssistant):
        """Test that when a server sends a new value for the same cookie name, it is updated."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            url = "https://example.com/page"

            # First request sets session=v1
            respx.get(url).mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "session=v1; Path=/"},
                )
            )
            await session.async_request("first", url)

            # Second request updates session=v2
            respx.get(url).mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "session=v2; Path=/"},
                )
            )
            await session.async_request("second", url)

            # Third request — should send session=v2, not v1
            route = respx.get("https://example.com/check").mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            await session.async_request("check", "https://example.com/check")

            cookies = route.calls.last.request.headers.get("cookie", "")
            assert "session=v2" in cookies
            assert "session=v1" not in cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookies_persist_across_many_requests(self, hass: HomeAssistant):
        """Test that cookies persist over many sequential requests."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            # Set cookie on first request
            respx.get("https://example.com/init").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "persistent=keepme; Path=/"},
                )
            )
            await session.async_request("init", "https://example.com/init")

            # Make 5 subsequent requests without setting cookies
            for i in range(5):
                route = respx.get(f"https://example.com/page{i}").mock(
                    return_value=respx.MockResponse(200, text=f"Page {i}")
                )
                await session.async_request(f"page{i}", f"https://example.com/page{i}")

                cookies = route.calls.last.request.headers.get("cookie", "")
                assert "persistent=keepme" in cookies, f"Cookie missing on request {i}"
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_multiple_set_cookie_headers(self, hass: HomeAssistant):
        """Test that multiple cookies set in a single response all persist."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            url = "https://example.com/login"
            # respx can set multiple cookies via headers list
            respx.get(url).mock(
                return_value=httpx.Response(
                    200,
                    text="OK",
                    headers=[
                        ("Set-Cookie", "auth_token=tok123; Path=/"),
                        ("Set-Cookie", "user_id=usr456; Path=/"),
                        ("Set-Cookie", "prefs=dark_mode; Path=/"),
                    ],
                )
            )

            await session.async_request("login", url)

            # Verify all cookies are sent in subsequent request
            check_route = respx.get("https://example.com/api").mock(
                return_value=respx.MockResponse(200, text="Data")
            )
            await session.async_request("api", "https://example.com/api")

            cookies = check_route.calls.last.request.headers.get("cookie", "")
            assert "auth_token=tok123" in cookies
            assert "user_id=usr456" in cookies
            assert "prefs=dark_mode" in cookies
        finally:
            await session.async_close()


# ============================================================================
# Cookie Persistence in Form Auth Flow
# ============================================================================


class TestCookiePersistenceInFormAuth:
    """Test cookie persistence through the form authentication workflow."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookies_from_form_page_reach_form_submit(self, hass: HomeAssistant):
        """Test that cookies set when fetching the form page are sent with the form POST."""
        conf = make_form_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            # Form page sets a CSRF cookie
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(
                    200, text=LOGIN_PAGE_HTML,
                    headers={"Set-Cookie": "csrf_cookie=csrf_val; Path=/"},
                )
            )
            submit_route = respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)
            await request_manager.get_content()

            submit_cookies = submit_route.calls.last.request.headers.get("cookie", "")
            assert "csrf_cookie=csrf_val" in submit_cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookies_from_form_submit_reach_data_page(self, hass: HomeAssistant):
        """Test that cookies set during form submission reach the data page request."""
        conf = make_form_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "auth_session=sess_abc; Path=/"},
                )
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)
            await request_manager.get_content()

            data_cookies = data_route.calls.last.request.headers.get("cookie", "")
            assert "auth_session=sess_abc" in data_cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_all_cookies_accumulate_through_entire_flow(self, hass: HomeAssistant):
        """Test that cookies from all three stages (form page, submit, data) accumulate."""
        conf = make_form_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            # Stage 1: Form page sets cookie_1
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(
                    200, text=LOGIN_PAGE_HTML,
                    headers={"Set-Cookie": "cookie_1=from_form_page; Path=/"},
                )
            )
            # Stage 2: Form submit sets cookie_2
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "cookie_2=from_submit; Path=/"},
                )
            )
            # Stage 3: Data page — all cookies should be present
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)
            await request_manager.get_content()

            data_cookies = data_route.calls.last.request.headers.get("cookie", "")
            assert "cookie_1=from_form_page" in data_cookies
            assert "cookie_2=from_submit" in data_cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookies_persist_across_scrape_cycles_with_submit_once(
        self, hass: HomeAssistant
    ):
        """Test cookies from first auth persist on subsequent cycles when submit_once=True."""
        conf = make_form_conf(form_submit={"submit_once": True, "resubmit_on_error": False})
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(
                    200, text=LOGIN_PAGE_HTML,
                    headers={"Set-Cookie": "session=first_auth; Path=/"},
                )
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "auth_tok=persistent_tok; Path=/"},
                )
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            # First cycle — full auth flow
            await request_manager.get_content()
            first_cookies = data_route.calls.last.request.headers.get("cookie", "")
            assert "session=first_auth" in first_cookies
            assert "auth_tok=persistent_tok" in first_cookies

            # Second cycle — no re-auth (submit_once), but cookies must persist
            await request_manager.get_content()
            second_cookies = data_route.calls.last.request.headers.get("cookie", "")
            assert "session=first_auth" in second_cookies
            assert "auth_tok=persistent_tok" in second_cookies

            # Third cycle — verify stability
            await request_manager.get_content()
            third_cookies = data_route.calls.last.request.headers.get("cookie", "")
            assert "session=first_auth" in third_cookies
            assert "auth_tok=persistent_tok" in third_cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookies_updated_on_reauth(self, hass: HomeAssistant):
        """Test that cookies are updated when re-authentication occurs."""
        conf = make_form_conf(
            form_submit={"submit_once": True, "resubmit_on_error": True}
        )
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            submit_route = respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "session=tok_v1; Path=/"},
                )
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            # First auth
            await request_manager.get_content()
            first_cookies = data_route.calls.last.request.headers.get("cookie", "")
            assert "session=tok_v1" in first_cookies

            # Update mock to return new cookie on resubmit
            submit_route.mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "session=tok_v2; Path=/"},
                )
            )

            # Force reauth
            await request_manager.get_content(force_reauth=True)
            reauth_cookies = data_route.calls.last.request.headers.get("cookie", "")
            assert "session=tok_v2" in reauth_cookies
            assert "session=tok_v1" not in reauth_cookies
        finally:
            await session.async_close()


# ============================================================================
# Cookie Edge Cases
# ============================================================================


class TestCookieEdgeCases:
    """Test edge cases in cookie handling."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_empty_cookie_value(self, hass: HomeAssistant):
        """Test that cookies with empty values are handled correctly."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            respx.get("https://example.com/page").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "empty_cookie=; Path=/"},
                )
            )
            await session.async_request("first", "https://example.com/page")

            route = respx.get("https://example.com/next").mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            await session.async_request("next", "https://example.com/next")

            # httpx should still send the cookie even with empty value
            cookies = route.calls.last.request.headers.get("cookie", "")
            assert "empty_cookie=" in cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookie_with_special_characters(self, hass: HomeAssistant):
        """Test that cookies with URL-encoded special characters are handled."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            respx.get("https://example.com/page").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "data=hello%20world; Path=/"},
                )
            )
            await session.async_request("first", "https://example.com/page")

            route = respx.get("https://example.com/next").mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            await session.async_request("next", "https://example.com/next")

            cookies = route.calls.last.request.headers.get("cookie", "")
            assert "data=hello%20world" in cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_no_cookies_when_none_set(self, hass: HomeAssistant):
        """Test that no cookie header is sent when no cookies have been set."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            route = respx.get("https://example.com/page").mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            await session.async_request("test", "https://example.com/page")

            # No cookie header should be present (or it should be empty)
            request = route.calls.last.request
            cookie_header = request.headers.get("cookie", "")
            assert cookie_header == ""
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookies_not_shared_between_sessions(self, hass: HomeAssistant):
        """Test that two separate HttpSession instances do not share cookies."""
        config = make_http_config()
        session1 = HttpSession(config_name="session1", hass=hass, http_config=config)
        session2 = HttpSession(config_name="session2", hass=hass, http_config=config)

        try:
            url = "https://example.com/page"

            # Session 1 gets a cookie
            respx.get(url).mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "session1_cookie=only_for_s1; Path=/"},
                )
            )
            await session1.async_request("test", url)

            # Session 2 makes a request — should NOT have session1's cookie
            respx.get(url).mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            route = respx.get("https://example.com/check").mock(
                return_value=respx.MockResponse(200, text="OK")
            )

            await session2.async_request("test", "https://example.com/check")

            cookies = route.calls.last.request.headers.get("cookie", "")
            assert "session1_cookie" not in cookies
        finally:
            await session1.async_close()
            await session2.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookie_with_long_value(self, hass: HomeAssistant):
        """Test that cookies with long values (like JWTs) persist correctly."""
        config = make_http_config()
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"

        try:
            respx.get("https://example.com/auth").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": f"jwt={jwt_like}; Path=/"},
                )
            )
            await session.async_request("auth", "https://example.com/auth")

            route = respx.get("https://example.com/api").mock(
                return_value=respx.MockResponse(200, text="Data")
            )
            await session.async_request("api", "https://example.com/api")

            cookies = route.calls.last.request.headers.get("cookie", "")
            assert f"jwt={jwt_like}" in cookies
        finally:
            await session.async_close()
