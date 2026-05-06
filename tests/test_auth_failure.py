"""Tests for authentication failure and re-authentication flows.

These tests verify the component's behavior when authentication fails,
including:
- HTTP 401/403 responses during form submission
- Form page returning no form element
- Auth recovery via resubmit_on_error
- Auth failure with submit_once flag interactions
- Coordinator-level force_reauth behavior
- Basic/digest auth failure handling
- Re-auth restoring session after form submit error
"""

import httpx
import pytest
import respx
from homeassistant.core import HomeAssistant
from httpx import RequestError, TimeoutException

from custom_components.multiscrape.coordinator import \
    create_content_request_manager
from custom_components.multiscrape.form_auth import (FormAuthConfig,
                                                     FormAuthenticator)
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

NO_FORM_HTML = """
<html><body>
<h1>Access Denied</h1>
<p>Your session has expired. Please try again.</p>
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


def make_form_config(**overrides):
    """Create a FormAuthConfig with sensible defaults."""
    defaults = {
        "parser": "html.parser",
        "headers_renderer": _NOOP_HEADERS,
        "params_renderer": _NOOP_PARAMS,
        "data_renderer": _NOOP_DATA,
    }
    return FormAuthConfig(**{**defaults, **overrides})


def make_form_session(hass, form_config, http_config=None):
    """Create an HttpSession with a FormAuthenticator wired up."""
    config = http_config or make_http_config()
    session = HttpSession(config_name="test", hass=hass, http_config=config)
    authenticator = FormAuthenticator(
        config_name="test",
        config=form_config,
        execute_request=session._execute_request,
    )
    session._form_authenticator = authenticator
    return session


def make_full_conf(**form_overrides):
    """Create a full config dict for create_http_session with form_submit."""
    form_defaults = {
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
    }
    form_defaults.update(form_overrides)

    return {
        "resource": "https://site.com/data",
        "method": "get",
        "verify_ssl": True,
        "timeout": 10,
        "parser": "html.parser",
        "form_submit": form_defaults,
    }


# ============================================================================
# Basic Auth Failure Tests
# ============================================================================


class TestBasicAuthFailure:
    """Test HTTP basic/digest authentication failure scenarios."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_basic_auth_401_raises_http_error(self, hass: HomeAssistant):
        """Test that a 401 response with basic auth raises an HTTPStatusError."""
        config = make_http_config(username="user", password="wrong_pass")
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            respx.get("https://example.com/protected").mock(
                return_value=respx.MockResponse(
                    401, text="Unauthorized",
                    headers={"WWW-Authenticate": "Basic realm=\"test\""},
                )
            )

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session.async_request("test", "https://example.com/protected")

            assert exc_info.value.response.status_code == 401
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_basic_auth_403_raises_http_error(self, hass: HomeAssistant):
        """Test that a 403 Forbidden response raises an HTTPStatusError."""
        config = make_http_config(username="user", password="pass")
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            respx.get("https://example.com/admin").mock(
                return_value=respx.MockResponse(403, text="Forbidden")
            )

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session.async_request("test", "https://example.com/admin")

            assert exc_info.value.response.status_code == 403
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_auth_succeeds_after_prior_failure(self, hass: HomeAssistant):
        """Test that auth can succeed on retry after a prior failure."""
        config = make_http_config(username="user", password="pass")
        session = HttpSession(config_name="test", hass=hass, http_config=config)

        try:
            url = "https://example.com/protected"

            # First attempt fails
            route = respx.get(url).mock(
                return_value=respx.MockResponse(401, text="Unauthorized")
            )

            with pytest.raises(httpx.HTTPStatusError):
                await session.async_request("attempt1", url)

            # Second attempt succeeds (e.g. server came back, credentials rotated)
            route.mock(return_value=respx.MockResponse(200, text="Welcome"))

            response = await session.async_request("attempt2", url)
            assert response.status_code == 200
            assert response.text == "Welcome"
        finally:
            await session.async_close()


# ============================================================================
# Form Auth Failure Tests
# ============================================================================


class TestFormAuthFailure:
    """Test form authentication failure scenarios."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_page_returns_no_form_raises_value_error(self, hass: HomeAssistant):
        """Test that a form page without a matching form element raises ValueError."""
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
            input_values={"user": "admin"},
        )
        session = make_form_session(hass, form_config)

        try:
            respx.get("https://example.com/login").mock(
                return_value=respx.MockResponse(200, text=NO_FORM_HTML)
            )

            with pytest.raises(ValueError, match="Could not find form"):
                await session.ensure_authenticated("https://example.com/main")
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_page_http_error_raises(self, hass: HomeAssistant):
        """Test that an HTTP error when fetching the form page is propagated."""
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
            input_values={"user": "admin"},
        )
        session = make_form_session(hass, form_config)

        try:
            respx.get("https://example.com/login").mock(
                return_value=respx.MockResponse(500, text="Internal Server Error")
            )

            with pytest.raises(httpx.HTTPStatusError):
                await session.ensure_authenticated("https://example.com/main")
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_submit_returns_401(self, hass: HomeAssistant):
        """Test that a 401 from form submission is propagated as HTTPStatusError."""
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
            input_values={"user": "admin", "pass": "wrong"},
        )
        session = make_form_session(hass, form_config)

        try:
            respx.get("https://example.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            # Form action in LOGIN_PAGE_HTML is "/auth/submit"
            respx.post("https://example.com/auth/submit").mock(
                return_value=respx.MockResponse(401, text="Invalid credentials")
            )

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session.ensure_authenticated("https://example.com/main")

            assert exc_info.value.response.status_code == 401
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_submit_returns_403(self, hass: HomeAssistant):
        """Test that a 403 from form submission is propagated."""
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
            input_values={"user": "banned_user", "pass": "secret"},
        )
        session = make_form_session(hass, form_config)

        try:
            respx.get("https://example.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            # Form action in LOGIN_PAGE_HTML is "/auth/submit"
            respx.post("https://example.com/auth/submit").mock(
                return_value=respx.MockResponse(403, text="Account suspended")
            )

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await session.ensure_authenticated("https://example.com/main")

            assert exc_info.value.response.status_code == 403
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_page_timeout_raises(self, hass: HomeAssistant):
        """Test that a timeout when fetching the form page is propagated."""
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
        )
        session = make_form_session(hass, form_config)

        try:
            respx.get("https://example.com/login").mock(
                side_effect=TimeoutException("Connection timed out")
            )

            with pytest.raises(TimeoutException):
                await session.ensure_authenticated("https://example.com/main")
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_page_connection_error_raises(self, hass: HomeAssistant):
        """Test that a connection error when fetching the form page is propagated."""
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
        )
        session = make_form_session(hass, form_config)

        try:
            respx.get("https://example.com/login").mock(
                side_effect=RequestError("Connection refused")
            )

            with pytest.raises(RequestError):
                await session.ensure_authenticated("https://example.com/main")
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_submit_timeout_raises(self, hass: HomeAssistant):
        """Test that a timeout during form submission is propagated."""
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
            input_values={"user": "admin"},
        )
        session = make_form_session(hass, form_config)

        try:
            respx.get("https://example.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            # Form action in LOGIN_PAGE_HTML is "/auth/submit"
            respx.post("https://example.com/auth/submit").mock(
                side_effect=TimeoutException("Form submit timed out")
            )

            with pytest.raises(TimeoutException):
                await session.ensure_authenticated("https://example.com/main")
        finally:
            await session.async_close()


# ============================================================================
# Re-authentication Flow Tests
# ============================================================================


class TestReauthFlow:
    """Test the re-authentication flow triggered by errors."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_invalidate_auth_enables_resubmit(self, hass: HomeAssistant):
        """Test that invalidate_auth sets _should_submit back to True."""
        form_config = make_form_config(
            input_values={"user": "admin"},
            submit_once=True,
            resubmit_on_error=True,
        )
        session = make_form_session(hass, form_config)

        try:
            respx.post("https://example.com/main").mock(
                return_value=respx.MockResponse(200, text="OK")
            )

            # First submit
            await session.ensure_authenticated("https://example.com/main")
            assert not session._form_authenticator._should_submit

            # Invalidate
            session.invalidate_auth()
            assert session._form_authenticator._should_submit

            # Re-submit should now happen
            result = await session.ensure_authenticated("https://example.com/main")
            assert result == "OK"
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_invalidate_auth_no_op_when_resubmit_disabled(self, hass: HomeAssistant):
        """Test that invalidate_auth does nothing when resubmit_on_error=False."""
        form_config = make_form_config(
            input_values={"user": "admin"},
            submit_once=True,
            resubmit_on_error=False,
        )
        session = make_form_session(hass, form_config)

        try:
            respx.post("https://example.com/main").mock(
                return_value=respx.MockResponse(200, text="OK")
            )

            await session.ensure_authenticated("https://example.com/main")
            assert not session._form_authenticator._should_submit

            # invalidate_auth should NOT set _should_submit back
            session.invalidate_auth()
            assert not session._form_authenticator._should_submit
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_reauth_after_data_page_error(self, hass: HomeAssistant):
        """Test that force_reauth triggers re-auth when data page previously failed."""
        conf = make_full_conf(submit_once=True, resubmit_on_error=True)
        session = create_http_session("test", conf, hass, None)

        try:
            login_route = respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            # First cycle — form submitted
            await request_manager.get_content()
            assert login_route.call_count == 1

            # Second cycle — no reauth (submit_once)
            await request_manager.get_content()
            assert login_route.call_count == 1

            # Third cycle — force reauth (simulating coordinator error recovery)
            await request_manager.get_content(force_reauth=True)
            assert login_route.call_count == 2
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_reauth_recovers_after_expired_session(self, hass: HomeAssistant):
        """Test end-to-end: first auth works, second cycle gets 401, reauth fixes it."""
        conf = make_full_conf(submit_once=True, resubmit_on_error=True)
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            # First cycle — works fine
            content = await request_manager.get_content()
            assert "21.5" in content

            # Simulate expired session — data page returns 401
            data_route.mock(return_value=respx.MockResponse(401, text="Session expired"))

            # This will raise because 401 raises HTTPStatusError
            with pytest.raises(httpx.HTTPStatusError):
                await request_manager.get_content()

            # Now reauth + data page works again
            data_route.mock(return_value=respx.MockResponse(200, text=DATA_PAGE_HTML))
            content = await request_manager.get_content(force_reauth=True)
            assert "21.5" in content
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_multiple_reauth_cycles(self, hass: HomeAssistant):
        """Test that multiple reauth cycles work correctly."""
        conf = make_full_conf(submit_once=True, resubmit_on_error=True)
        session = create_http_session("test", conf, hass, None)

        try:
            login_route = respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(200, text="OK")
            )
            respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            # Cycle 1: initial auth
            await request_manager.get_content()
            assert login_route.call_count == 1

            # Cycle 2: force reauth
            await request_manager.get_content(force_reauth=True)
            assert login_route.call_count == 2

            # Cycle 3: normal (no reauth since submit_once resets)
            await request_manager.get_content()
            assert login_route.call_count == 2

            # Cycle 4: force reauth again
            await request_manager.get_content(force_reauth=True)
            assert login_route.call_count == 3
        finally:
            await session.async_close()


# ============================================================================
# ContentRequestManager Auth Failure Recovery Tests
# ============================================================================


class TestContentRequestManagerAuthRecovery:
    """Test that ContentRequestManager gracefully handles auth failures."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_auth_failure_falls_through_to_data_page(self, hass: HomeAssistant):
        """Test that when form auth fails, get_content still fetches the data page."""
        conf = make_full_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            # Form page returns no form — will raise ValueError
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=NO_FORM_HTML)
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)
            content = await request_manager.get_content()

            # Should fall through to fetching data page directly
            assert data_route.called
            assert "21.5" in content
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_auth_timeout_falls_through_to_data_page(self, hass: HomeAssistant):
        """Test that when form page times out, get_content still tries data page."""
        conf = make_full_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                side_effect=TimeoutException("Login page timed out")
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)
            content = await request_manager.get_content()

            assert data_route.called
            assert "21.5" in content
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_auth_500_falls_through_to_data_page(self, hass: HomeAssistant):
        """Test that when form page returns 500, get_content still tries data page."""
        conf = make_full_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(500, text="Server Error")
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)
            content = await request_manager.get_content()

            assert data_route.called
            assert "21.5" in content
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_both_form_and_data_fail_raises(self, hass: HomeAssistant):
        """Test that when both form auth and data page fail, the error propagates."""
        conf = make_full_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            # Form auth fails
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=NO_FORM_HTML)
            )
            # Data page also fails
            respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(503, text="Service Unavailable")
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await request_manager.get_content()

            assert exc_info.value.response.status_code == 503
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_auth_recovery_after_intermittent_failure(self, hass: HomeAssistant):
        """Test that form auth recovers after an intermittent failure.

        Cycle 1: Form auth fails, data page works (degraded mode)
        Cycle 2: Form auth succeeds, full flow works
        """
        conf = make_full_conf(submit_once=False)
        session = create_http_session("test", conf, hass, None)

        try:
            login_route = respx.get("https://site.com/login")
            submit_route = respx.post("https://site.com/auth/submit")
            data_route = respx.get("https://site.com/data")

            # Cycle 1: form page fails (no form), data page works
            login_route.mock(return_value=respx.MockResponse(200, text=NO_FORM_HTML))
            data_route.mock(return_value=respx.MockResponse(200, text=DATA_PAGE_HTML))

            request_manager = create_content_request_manager("test", conf, hass, session)
            content = await request_manager.get_content()
            assert "21.5" in content

            # Cycle 2: form page recovers, full auth flow works
            login_route.mock(return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML))
            submit_route.mock(return_value=respx.MockResponse(200, text="OK"))

            content = await request_manager.get_content()
            assert "21.5" in content
            assert submit_route.called
        finally:
            await session.async_close()


# ============================================================================
# Form Auth State Management Tests
# ============================================================================


class TestFormAuthStateManagement:
    """Test the _should_submit state management in various scenarios."""

    @pytest.mark.unit
    def test_initial_state_should_submit_is_true(self, hass: HomeAssistant):
        """Test that a new FormAuthenticator starts with _should_submit=True."""
        form_config = make_form_config()
        authenticator = FormAuthenticator(
            config_name="test",
            config=form_config,
            execute_request=lambda **kwargs: None,
        )
        assert authenticator._should_submit is True

    @pytest.mark.unit
    def test_form_variables_empty_initially(self, hass: HomeAssistant):
        """Test that form_variables is empty initially."""
        form_config = make_form_config()
        authenticator = FormAuthenticator(
            config_name="test",
            config=form_config,
            execute_request=lambda **kwargs: None,
        )
        assert authenticator.form_variables == {}

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_submit_once_true_disables_after_first_submit(self, hass: HomeAssistant):
        """Test that submit_once=True sets _should_submit=False after first submit."""
        form_config = make_form_config(
            input_values={"user": "admin"},
            submit_once=True,
        )
        session = make_form_session(hass, form_config)

        try:
            respx.post("https://example.com/main").mock(
                return_value=respx.MockResponse(200, text="OK")
            )

            assert session._form_authenticator._should_submit is True
            await session.ensure_authenticated("https://example.com/main")
            assert session._form_authenticator._should_submit is False
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_submit_once_false_keeps_submitting(self, hass: HomeAssistant):
        """Test that submit_once=False keeps _should_submit=True after submit."""
        form_config = make_form_config(
            input_values={"user": "admin"},
            submit_once=False,
        )
        session = make_form_session(hass, form_config)

        try:
            submit_route = respx.post("https://example.com/main").mock(
                return_value=respx.MockResponse(200, text="OK")
            )

            # Submit three times — should always submit
            await session.ensure_authenticated("https://example.com/main")
            await session.ensure_authenticated("https://example.com/main")
            await session.ensure_authenticated("https://example.com/main")

            assert submit_route.call_count == 3
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_invalidate_then_submit_once_cycle(self, hass: HomeAssistant):
        """Test full cycle: submit_once → skip → invalidate → submit again → skip."""
        form_config = make_form_config(
            input_values={"user": "admin"},
            submit_once=True,
            resubmit_on_error=True,
        )
        session = make_form_session(hass, form_config)

        try:
            submit_route = respx.post("https://example.com/main").mock(
                return_value=respx.MockResponse(200, text="OK")
            )

            # Step 1: Submit (first time)
            await session.ensure_authenticated("https://example.com/main")
            assert submit_route.call_count == 1

            # Step 2: Skip (submit_once)
            await session.ensure_authenticated("https://example.com/main")
            assert submit_route.call_count == 1

            # Step 3: Invalidate
            session.invalidate_auth()

            # Step 4: Submit again
            await session.ensure_authenticated("https://example.com/main")
            assert submit_route.call_count == 2

            # Step 5: Skip again (submit_once re-engaged)
            await session.ensure_authenticated("https://example.com/main")
            assert submit_route.call_count == 2
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_auth_failure_does_not_set_submit_once_flag(
        self, hass: HomeAssistant
    ):
        """Test that when form auth fails (raises), submit_once flag is not toggled.

        If form submission fails (e.g. form not found), _should_submit should
        remain True so it retries next time.
        """
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
            submit_once=True,
            resubmit_on_error=True,
        )
        session = make_form_session(hass, form_config)

        try:
            # Form page has no form — will raise ValueError
            respx.get("https://example.com/login").mock(
                return_value=respx.MockResponse(200, text=NO_FORM_HTML)
            )

            with pytest.raises(ValueError):
                await session.ensure_authenticated("https://example.com/main")

            # _should_submit should still be True since auth failed before
            # reaching the submit_once logic
            assert session._form_authenticator._should_submit is True
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_submit_once_not_set_on_form_post_http_error(
        self, hass: HomeAssistant
    ):
        """Test that submit_once flag stays True when form POST returns 401.

        HTTP errors from the form POST throw before reaching the submit_once
        flag-setting line, so the flag should remain True for retry.
        """
        form_config = make_form_config(
            resource="https://example.com/login",
            select="#loginform",
            input_values={"user": "admin"},
            submit_once=True,
            resubmit_on_error=True,
        )
        session = make_form_session(hass, form_config)

        try:
            respx.get("https://example.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            # Form POST returns 401 — auth rejected
            respx.post("https://example.com/auth/submit").mock(
                return_value=respx.MockResponse(401, text="Invalid credentials")
            )

            with pytest.raises(httpx.HTTPStatusError):
                await session.ensure_authenticated("https://example.com/main")

            # _should_submit must still be True — auth failed, should retry
            assert session._form_authenticator._should_submit is True
        finally:
            await session.async_close()


# ============================================================================
# Auth 401/403 Rejection Tests (must NOT fall through)
# ============================================================================


class TestAuth401403Rejection:
    """Test that 401/403 from form auth propagate and do NOT fall through.

    When form authentication is rejected (401/403), fetching the data page
    without auth would return unreliable data (login page, access denied, etc.).
    The component must raise instead of silently continuing.
    """

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_submit_401_does_not_fall_through(self, hass: HomeAssistant):
        """Test that a 401 from form submit raises through get_content."""
        conf = make_full_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(401, text="Bad credentials")
            )
            # Data page should NOT be fetched
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await request_manager.get_content()

            assert exc_info.value.response.status_code == 401
            # Data page must NOT have been fetched
            assert not data_route.called
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_submit_403_does_not_fall_through(self, hass: HomeAssistant):
        """Test that a 403 from form submit raises through get_content."""
        conf = make_full_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(403, text="Account locked")
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await request_manager.get_content()

            assert exc_info.value.response.status_code == 403
            assert not data_route.called
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_page_401_does_not_fall_through(self, hass: HomeAssistant):
        """Test that a 401 from the form page itself raises through get_content."""
        conf = make_full_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            # Form page returns 401
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(401, text="Unauthorized")
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await request_manager.get_content()

            assert exc_info.value.response.status_code == 401
            assert not data_route.called
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_form_500_still_falls_through(self, hass: HomeAssistant):
        """Test that a 500 from form page still falls through (not auth rejection)."""
        conf = make_full_conf()
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(500, text="Internal Server Error")
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)
            content = await request_manager.get_content()

            # 500 is not an auth rejection — should fall through
            assert data_route.called
            assert "21.5" in content
        finally:
            await session.async_close()


# ============================================================================
# Cookie Jar Clearing on Reauth Tests
# ============================================================================


class TestCookieJarClearingOnReauth:
    """Test that cookie jar is cleared when auth is invalidated."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_invalidate_auth_clears_cookie_jar(self, hass: HomeAssistant):
        """Test that invalidate_auth() clears the httpx client cookie jar."""
        conf = make_full_conf(submit_once=True, resubmit_on_error=True)
        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "old_session=abc; Path=/"},
                )
            )
            data_route = respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            # First cycle — sets cookies
            await request_manager.get_content()
            first_cookies = data_route.calls.last.request.headers.get("cookie", "")
            assert "old_session=abc" in first_cookies

            # Invalidate — should clear cookies
            # Update mock to return a new cookie name on reauth
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "new_session=xyz; Path=/"},
                )
            )

            await request_manager.get_content(force_reauth=True)
            reauth_cookies = data_route.calls.last.request.headers.get("cookie", "")

            # Old cookie must be gone after reauth; new cookie present
            assert "old_session=abc" not in reauth_cookies
            assert "new_session=xyz" in reauth_cookies
        finally:
            await session.async_close()

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_cookie_jar_empty_after_invalidate(self, hass: HomeAssistant):
        """Test that the raw cookie jar is empty immediately after invalidation."""
        form_config = make_form_config(
            input_values={"user": "admin"},
            submit_once=True,
            resubmit_on_error=True,
        )
        session = make_form_session(hass, form_config)

        try:
            respx.post("https://example.com/main").mock(
                return_value=respx.MockResponse(
                    200, text="OK",
                    headers={"Set-Cookie": "sess=tok123; Path=/"},
                )
            )

            await session.ensure_authenticated("https://example.com/main")
            assert len(session._client.cookies) > 0

            session.invalidate_auth()
            assert len(session._client.cookies) == 0
        finally:
            await session.async_close()


# ============================================================================
# Stale Form Variables Tests
# ============================================================================


class TestStaleFormVariables:
    """Test behavior of form_variables when reauth fails."""

    @pytest.mark.integration
    @pytest.mark.async_test
    @pytest.mark.http
    @pytest.mark.timeout(10)
    @respx.mock
    async def test_stale_variables_persist_after_failed_reauth(self, hass: HomeAssistant):
        """Test that old form_variables remain when reauth fails.

        This is the lesser evil vs. clearing them (which would break templates),
        but the code should log a warning about it.
        """
        from homeassistant.helpers.template import Template

        conf = make_full_conf(submit_once=True, resubmit_on_error=True)
        conf["form_submit"]["variables"] = [
            {
                "name": "token",
                "select": Template(".api-token", hass),
                "extract": "text",
            },
        ]
        conf["form_submit"]["parser"] = "html.parser"
        conf["form_submit"]["separator"] = ","

        TOKEN_PAGE = '<html><body><div class="api-token">tok_v1</div></body></html>'

        session = create_http_session("test", conf, hass, None)

        try:
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=LOGIN_PAGE_HTML)
            )
            respx.post("https://site.com/auth/submit").mock(
                return_value=respx.MockResponse(200, text=TOKEN_PAGE)
            )
            respx.get("https://site.com/data").mock(
                return_value=respx.MockResponse(200, text=DATA_PAGE_HTML)
            )

            request_manager = create_content_request_manager("test", conf, hass, session)

            # First cycle — variables scraped successfully
            await request_manager.get_content()
            assert session.form_variables["token"] == "tok_v1"

            # Simulate reauth where form page now returns no form
            respx.get("https://site.com/login").mock(
                return_value=respx.MockResponse(200, text=NO_FORM_HTML)
            )

            # Reauth fails (ValueError: could not find form) but falls through
            await request_manager.get_content(force_reauth=True)

            # Stale variables should still be there
            assert session.form_variables["token"] == "tok_v1"
        finally:
            await session.async_close()
