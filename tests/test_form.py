"""Integration tests for form submission functionality."""

import pytest
import respx
from homeassistant.const import CONF_NAME, CONF_RESOURCE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import (CONF_FORM_INPUT,
                                                 CONF_FORM_INPUT_FILTER,
                                                 CONF_FORM_RESUBMIT_ERROR,
                                                 CONF_FORM_SELECT,
                                                 CONF_FORM_SUBMIT_ONCE,
                                                 CONF_FORM_VARIABLES)
from custom_components.multiscrape.form import (FormSubmitter,
                                                create_form_submitter)


@pytest.fixture
def form_html():
    """Create HTML with a simple form."""
    return """
    <html>
        <body>
            <form action="/submit" method="POST" id="login">
                <input type="text" name="username" value="default_user">
                <input type="password" name="password" value="">
                <input type="hidden" name="csrf_token" value="abc123">
                <input type="submit" value="Login">
            </form>
        </body>
    </html>
    """


@pytest.fixture
def form_html_with_filter():
    """Create HTML with form that has fields to filter."""
    return """
    <html>
        <body>
            <form action="/login" method="POST">
                <input type="text" name="username" value="">
                <input type="password" name="password" value="">
                <input type="hidden" name="session_id" value="old_session">
                <input type="submit" name="submit_button" value="Login">
            </form>
        </body>
    </html>
    """


@pytest.fixture
def form_html_no_action():
    """Create HTML with form that has no action attribute."""
    return """
    <html>
        <body>
            <form method="POST">
                <input type="text" name="username" value="">
                <input type="password" name="password" value="">
            </form>
        </body>
    </html>
    """


@pytest.fixture
def basic_form_config(hass: HomeAssistant):
    """Create basic form configuration."""
    return {
        CONF_RESOURCE: "https://example.com/form",
        CONF_FORM_SELECT: "form#login",
        CONF_FORM_INPUT: {"username": "testuser", "password": "testpass"},
        CONF_FORM_INPUT_FILTER: [],
        CONF_FORM_SUBMIT_ONCE: False,
        CONF_FORM_RESUBMIT_ERROR: False,
        CONF_FORM_VARIABLES: [],
    }


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_initialization(hass: HomeAssistant, http_wrapper):
    """Test FormSubmitter initializes correctly."""
    # Arrange & Act
    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource="https://example.com/login",
        select="form",
        input_values={"field": "value"},
        input_filter=["unwanted"],
        submit_once=True,
        resubmit_error=True,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Assert
    assert form_submitter._config_name == "test_form"
    assert form_submitter._select == "form"
    assert form_submitter._input_values == {"field": "value"}
    assert form_submitter._submit_once is True
    assert form_submitter._resubmit_error is True
    assert form_submitter._should_submit is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_basic_submit(hass: HomeAssistant, http_wrapper, form_html):
    """Test basic form submission."""
    # Arrange
    form_page_url = "https://example.com/login"
    submit_url = "https://example.com/submit"

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=form_html))
    submit_route = respx.post(submit_url).mock(
        return_value=respx.MockResponse(200, text="Login successful")
    )

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form#login",
        input_values={"username": "testuser", "password": "testpass"},
        input_filter=[],
        submit_once=False,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act
    content, cookies = await form_submitter.async_submit("https://example.com/main")

    # Assert
    assert content is None  # Returns None when form_resource is set
    assert submit_route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_with_input_filter(hass: HomeAssistant, http_wrapper, form_html_with_filter):
    """Test form submission with input field filtering."""
    # Arrange
    form_page_url = "https://example.com/login"
    submit_url = "https://example.com/login"

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=form_html_with_filter))
    submit_route = respx.post(submit_url).mock(
        return_value=respx.MockResponse(200, text="Success")
    )

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form",
        input_values={"username": "user", "password": "pass"},
        input_filter=["session_id", "submit_button"],  # Filter out these fields
        submit_once=False,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act
    await form_submitter.async_submit("https://example.com/main")

    # Assert
    assert submit_route.called
    # Verify filtered fields are not in the payload
    assert form_submitter._payload.get("session_id") is None
    assert form_submitter._payload.get("submit_button") is None
    # Verify input values are in the payload
    assert form_submitter._payload.get("username") == "user"
    assert form_submitter._payload.get("password") == "pass"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_submit_once(hass: HomeAssistant, http_wrapper, form_html):
    """Test form submission with submit_once=True."""
    # Arrange
    form_page_url = "https://example.com/login"

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=form_html))
    respx.post("https://example.com/submit").mock(
        return_value=respx.MockResponse(200, text="Success")
    )

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form",
        input_values={},
        input_filter=[],
        submit_once=True,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act
    assert form_submitter.should_submit is True
    await form_submitter.async_submit("https://example.com/main")

    # Assert - should_submit should be False after first submission
    assert form_submitter.should_submit is False


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_resubmit_on_error(hass: HomeAssistant, http_wrapper):
    """Test form resubmission after error when resubmit_error=True."""
    # Arrange
    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource="https://example.com/login",
        select="form",
        input_values={},
        input_filter=[],
        submit_once=True,
        resubmit_error=True,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Simulate form already submitted once
    form_submitter._should_submit = False

    # Act
    form_submitter.notify_scrape_exception()

    # Assert - should_submit should be True again after exception
    assert form_submitter.should_submit is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_no_resubmit_on_error(hass: HomeAssistant, http_wrapper):
    """Test form does not resubmit after error when resubmit_error=False."""
    # Arrange
    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource="https://example.com/login",
        select="form",
        input_values={},
        input_filter=[],
        submit_once=True,
        resubmit_error=False,  # Don't resubmit
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Simulate form already submitted once
    form_submitter._should_submit = False

    # Act
    form_submitter.notify_scrape_exception()

    # Assert - should_submit should remain False
    assert form_submitter.should_submit is False


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_without_select(hass: HomeAssistant, http_wrapper):
    """Test form submission without select (all input from config)."""
    # Arrange
    submit_url = "https://example.com/api/login"
    submit_route = respx.post(submit_url).mock(
        return_value=respx.MockResponse(200, text="Success")
    )

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=None,
        select=None,  # No form scraping
        input_values={"username": "user", "password": "pass"},
        input_filter=[],
        submit_once=False,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act
    content, cookies = await form_submitter.async_submit(submit_url)

    # Assert
    assert submit_route.called
    assert content == "Success"  # Returns content when form_resource is None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_form_not_found(hass: HomeAssistant, http_wrapper):
    """Test form submission raises error when form selector doesn't match."""
    # Arrange
    form_page_url = "https://example.com/login"
    html_no_form = "<html><body><p>No form here</p></body></html>"

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=html_no_form))

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form#nonexistent",
        input_values={},
        input_filter=[],
        submit_once=False,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act & Assert
    with pytest.raises(ValueError, match="Could not find form"):
        await form_submitter.async_submit("https://example.com/main")


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_no_action_attribute(hass: HomeAssistant, http_wrapper, form_html_no_action):
    """Test form submission when form has no action attribute."""
    # Arrange
    form_page_url = "https://example.com/login"

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=form_html_no_action))
    submit_route = respx.post(form_page_url).mock(
        return_value=respx.MockResponse(200, text="Success")
    )

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form",
        input_values={"username": "user", "password": "pass"},
        input_filter=[],
        submit_once=False,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act
    await form_submitter.async_submit("https://example.com/main")

    # Assert - should submit to form_resource when action is None
    assert submit_route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_relative_action(hass: HomeAssistant, http_wrapper):
    """Test form submission with relative action URL."""
    # Arrange
    form_page_url = "https://example.com/login"
    form_html = """
    <html>
        <body>
            <form action="auth/submit" method="POST">
                <input type="text" name="user" value="">
            </form>
        </body>
    </html>
    """

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=form_html))
    # urljoin will resolve relative URL
    submit_route = respx.post("https://example.com/auth/submit").mock(
        return_value=respx.MockResponse(200, text="Success")
    )

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form",
        input_values={"user": "testuser"},
        input_filter=[],
        submit_once=False,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act
    await form_submitter.async_submit("https://example.com/main")

    # Assert
    assert submit_route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_absolute_action(hass: HomeAssistant, http_wrapper):
    """Test form submission with absolute action URL."""
    # Arrange
    form_page_url = "https://example.com/login"
    form_html = """
    <html>
        <body>
            <form action="https://auth.example.com/submit" method="POST">
                <input type="text" name="user" value="">
            </form>
        </body>
    </html>
    """

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=form_html))
    submit_route = respx.post("https://auth.example.com/submit").mock(
        return_value=respx.MockResponse(200, text="Success")
    )

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form",
        input_values={"user": "testuser"},
        input_filter=[],
        submit_once=False,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act
    await form_submitter.async_submit("https://example.com/main")

    # Assert
    assert submit_route.called


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_get_input_fields_filters_none_names(hass: HomeAssistant, http_wrapper):
    """Test that input fields without name attribute are filtered out."""
    # Arrange
    form_page_url = "https://example.com/login"
    form_html = """
    <html>
        <body>
            <form action="/submit" method="POST">
                <input type="text" name="username" value="user">
                <input type="password" value="secret">
                <input type="submit" value="Submit">
            </form>
        </body>
    </html>
    """

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=form_html))
    submit_route = respx.post("https://example.com/submit").mock(
        return_value=respx.MockResponse(200, text="Success")
    )

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form",
        input_values={},
        input_filter=[],
        submit_once=False,
        resubmit_error=False,
        variables_selectors={},
        scraper=None,
        parser="lxml",
    )

    # Act
    await form_submitter.async_submit("https://example.com/main")

    # Assert
    assert submit_route.called
    # Only named input should be in payload
    assert "username" in form_submitter._payload
    assert len(form_submitter._payload) == 1


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
@respx.mock
async def test_form_submitter_with_variables(hass: HomeAssistant, http_wrapper, scraper):
    """Test form submission with variable extraction."""
    from custom_components.multiscrape.selector import Selector

    # Arrange
    form_page_url = "https://example.com/login"
    form_html = """
    <html>
        <body>
            <div class="session-token">abc123</div>
            <form action="/submit" method="POST">
                <input type="text" name="username" value="">
            </form>
        </body>
    </html>
    """

    # The submit response also needs the variable since that's what gets loaded into scraper
    submit_response = """
    <html>
        <body>
            <div class="session-token">abc123</div>
            <p>Success</p>
        </body>
    </html>
    """

    respx.get(form_page_url).mock(return_value=respx.MockResponse(200, text=form_html))
    submit_route = respx.post("https://example.com/submit").mock(
        return_value=respx.MockResponse(200, text=submit_response)
    )

    # Create variable selector
    from custom_components.multiscrape.const import CONF_EXTRACT, CONF_SELECT
    var_config = {
        CONF_NAME: "session_token",
        CONF_SELECT: Template(".session-token", hass),
        CONF_EXTRACT: "text",
    }
    var_selector = Selector(hass, var_config)

    form_submitter = FormSubmitter(
        config_name="test_form",
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        form_resource=form_page_url,
        select="form",
        input_values={"username": "user"},
        input_filter=[],
        submit_once=False,
        resubmit_error=False,
        variables_selectors={"session_token": var_selector},
        scraper=scraper,
        parser="lxml",
    )

    # Act
    await form_submitter.async_submit("https://example.com/main")
    variables = form_submitter.scrape_variables()

    # Assert
    assert submit_route.called
    assert "session_token" in variables
    assert variables["session_token"] == "abc123"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
async def test_create_form_submitter(hass: HomeAssistant, http_wrapper):
    """Test create_form_submitter factory function."""
    # Arrange
    config = {
        CONF_RESOURCE: "https://example.com/form",
        CONF_FORM_SELECT: "form",
        CONF_FORM_INPUT: {"field": "value"},
        CONF_FORM_INPUT_FILTER: ["unwanted"],
        CONF_FORM_SUBMIT_ONCE: True,
        CONF_FORM_RESUBMIT_ERROR: True,
        CONF_FORM_VARIABLES: [],
    }

    # Act
    form_submitter = create_form_submitter(
        config_name="test_form",
        config=config,
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        parser="lxml",
    )

    # Assert
    assert isinstance(form_submitter, FormSubmitter)
    assert form_submitter._form_resource == "https://example.com/form"
    assert form_submitter._select == "form"
    assert form_submitter._submit_once is True
    assert form_submitter._resubmit_error is True


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
@pytest.mark.filterwarnings("ignore:Setting per-request cookies:DeprecationWarning")
async def test_create_form_submitter_with_variables(hass: HomeAssistant, http_wrapper):
    """Test create_form_submitter with variable selectors."""
    # Arrange
    from custom_components.multiscrape.const import (CONF_EXTRACT, CONF_PARSER,
                                                     CONF_SELECT)

    config = {
        CONF_RESOURCE: "https://example.com/form",
        CONF_FORM_SELECT: "form",
        CONF_FORM_INPUT: {},
        CONF_FORM_INPUT_FILTER: [],
        CONF_FORM_SUBMIT_ONCE: False,
        CONF_FORM_RESUBMIT_ERROR: False,
        CONF_FORM_VARIABLES: [
            {
                CONF_NAME: "var1",
                CONF_SELECT: Template(".var1", hass),
                CONF_EXTRACT: "text",
            },
        ],
        CONF_PARSER: "lxml",
    }

    # Act
    form_submitter = create_form_submitter(
        config_name="test_form",
        config=config,
        hass=hass,
        http=http_wrapper,
        file_manager=None,
        parser="lxml",
    )

    # Assert
    assert isinstance(form_submitter, FormSubmitter)
    assert form_submitter._scraper is not None
    assert "var1" in form_submitter._variables_selectors
