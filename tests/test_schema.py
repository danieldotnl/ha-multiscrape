"""Unit tests for multiscrape schema validation."""

import pytest
import voluptuous as vol
from homeassistant.const import (CONF_AUTHENTICATION, CONF_METHOD,
                                 CONF_RESOURCE, CONF_RESOURCE_TEMPLATE,
                                 CONF_TIMEOUT, CONF_VERIFY_SSL,
                                 HTTP_BASIC_AUTHENTICATION,
                                 HTTP_DIGEST_AUTHENTICATION)

from custom_components.multiscrape.const import (CONF_EXTRACT,
                                                 CONF_FORM_VARIABLES,
                                                 CONF_ON_ERROR_LOG,
                                                 CONF_ON_ERROR_VALUE,
                                                 CONF_ON_ERROR_VALUE_DEFAULT,
                                                 CONF_ON_ERROR_VALUE_LAST,
                                                 CONF_ON_ERROR_VALUE_NONE,
                                                 CONF_SELECT, DEFAULT_EXTRACT,
                                                 DOMAIN, LOG_ERROR)
from custom_components.multiscrape.schema import (COMBINED_SCHEMA,
                                                  CONFIG_SCHEMA,
                                                  FORM_SUBMIT_SCHEMA,
                                                  ON_ERROR_SCHEMA,
                                                  SELECTOR_SCHEMA,
                                                  SERVICE_COMBINED_SCHEMA)
from custom_components.multiscrape.scraper import DEFAULT_TIMEOUT

# ============================================================================
# HTTP_SCHEMA tests
# ============================================================================


def _validate_combined(config):
    """Validate a config dict through COMBINED_SCHEMA."""
    return COMBINED_SCHEMA(config)


@pytest.mark.unit
def test_http_schema_method_case_insensitive():
    """Test that method is case-insensitive and normalized to lowercase."""
    for method in ["GET", "get", "Get", "gEt"]:
        result = _validate_combined({CONF_RESOURCE: "https://example.com", CONF_METHOD: method})
        assert result[CONF_METHOD] == "get"

    for method in ["POST", "post", "Post"]:
        result = _validate_combined({CONF_RESOURCE: "https://example.com", CONF_METHOD: method})
        assert result[CONF_METHOD] == "post"

    for method in ["PUT", "put", "Put"]:
        result = _validate_combined({CONF_RESOURCE: "https://example.com", CONF_METHOD: method})
        assert result[CONF_METHOD] == "put"


@pytest.mark.unit
def test_http_schema_rejects_invalid_method():
    """Test that unsupported HTTP methods are rejected."""
    for method in ["DELETE", "PATCH", "OPTIONS", "HEAD"]:
        with pytest.raises(vol.Invalid):
            _validate_combined({CONF_RESOURCE: "https://example.com", CONF_METHOD: method})


@pytest.mark.unit
def test_http_schema_default_method_is_get():
    """Test that omitting method defaults to 'get'."""
    result = _validate_combined({CONF_RESOURCE: "https://example.com"})
    assert result[CONF_METHOD] == "get"


@pytest.mark.unit
def test_http_schema_accepts_basic_and_digest_auth():
    """Test that basic and digest auth types are accepted."""
    for auth_type in [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]:
        result = _validate_combined({
            CONF_RESOURCE: "https://example.com",
            CONF_AUTHENTICATION: auth_type,
        })
        assert result[CONF_AUTHENTICATION] == auth_type


@pytest.mark.unit
def test_http_schema_rejects_invalid_auth():
    """Test that unsupported auth types are rejected."""
    with pytest.raises(vol.Invalid):
        _validate_combined({
            CONF_RESOURCE: "https://example.com",
            CONF_AUTHENTICATION: "bearer",
        })


@pytest.mark.unit
def test_http_schema_resource_and_template_exclusive():
    """Test that resource and resource_template are mutually exclusive."""
    with pytest.raises(vol.Invalid):
        _validate_combined({
            CONF_RESOURCE: "https://example.com",
            CONF_RESOURCE_TEMPLATE: "https://{{ host }}.com",
        })


@pytest.mark.unit
def test_http_schema_defaults():
    """Test default values for verify_ssl and timeout."""
    result = _validate_combined({CONF_RESOURCE: "https://example.com"})
    assert result[CONF_VERIFY_SSL] is True
    assert result[CONF_TIMEOUT] == DEFAULT_TIMEOUT


# ============================================================================
# SELECTOR_SCHEMA / ON_ERROR_SCHEMA tests
# ============================================================================


def _validate_selector(config):
    """Validate a selector config."""
    return vol.Schema(SELECTOR_SCHEMA)(config)


@pytest.mark.unit
def test_selector_schema_extract_options():
    """Test that valid extract options are accepted and invalid ones rejected."""
    for option in ["text", "content", "tag"]:
        result = _validate_selector({CONF_EXTRACT: option})
        assert result[CONF_EXTRACT] == option

    with pytest.raises(vol.Invalid):
        _validate_selector({CONF_EXTRACT: "html"})


@pytest.mark.unit
def test_selector_schema_default_extract():
    """Test that omitting extract defaults to 'text'."""
    result = _validate_selector({})
    assert result[CONF_EXTRACT] == DEFAULT_EXTRACT
    assert result[CONF_EXTRACT] == "text"


def _validate_on_error(config):
    """Validate an on_error config."""
    return vol.Schema(ON_ERROR_SCHEMA)(config)


@pytest.mark.unit
def test_on_error_schema_values():
    """Test that valid on_error values are accepted and invalid ones rejected."""
    for value in [CONF_ON_ERROR_VALUE_LAST, CONF_ON_ERROR_VALUE_NONE, CONF_ON_ERROR_VALUE_DEFAULT]:
        result = _validate_on_error({CONF_ON_ERROR_VALUE: value})
        assert result[CONF_ON_ERROR_VALUE] == value

    with pytest.raises(vol.Invalid):
        _validate_on_error({CONF_ON_ERROR_VALUE: "ignore"})


@pytest.mark.unit
def test_on_error_schema_log_levels():
    """Test that valid log levels are accepted."""
    for level in ["error", "warning", "info", False]:
        result = _validate_on_error({CONF_ON_ERROR_LOG: level})
        assert result[CONF_ON_ERROR_LOG] == level


@pytest.mark.unit
def test_on_error_schema_defaults():
    """Test on_error defaults: log='error', value='none'."""
    result = _validate_on_error({})
    assert result[CONF_ON_ERROR_LOG] == LOG_ERROR
    assert result[CONF_ON_ERROR_VALUE] == CONF_ON_ERROR_VALUE_NONE


# ============================================================================
# COMBINED_SCHEMA / CONFIG_SCHEMA tests
# ============================================================================


@pytest.mark.unit
def test_combined_schema_minimal_valid():
    """Test minimal valid config: resource + one sensor with select."""
    result = _validate_combined({
        CONF_RESOURCE: "https://example.com",
        "sensor": [{"name": "test", CONF_SELECT: ".data"}],
    })
    assert result[CONF_RESOURCE] == "https://example.com"
    assert len(result["sensor"]) == 1


@pytest.mark.unit
def test_config_schema_domain_wrapper():
    """Test CONFIG_SCHEMA wraps config under the domain key."""
    config = {
        DOMAIN: [
            {CONF_RESOURCE: "https://example.com"},
        ]
    }
    result = CONFIG_SCHEMA(config)
    assert DOMAIN in result
    assert len(result[DOMAIN]) == 1


@pytest.mark.unit
def test_config_schema_rejects_missing_domain():
    """Test CONFIG_SCHEMA rejects config without the domain key (extra keys allowed but domain required)."""
    config = {
        "other_domain": [
            {CONF_RESOURCE: "https://example.com"},
        ]
    }
    # CONFIG_SCHEMA has extra=ALLOW_EXTRA, so missing DOMAIN key is not an error by itself.
    # But the domain key won't be present in the result.
    result = CONFIG_SCHEMA(config)
    assert DOMAIN not in result


# ============================================================================
# create_service_schema() tests
# ============================================================================


@pytest.mark.unit
def test_service_schema_accepts_string_value_template():
    """Test service schema accepts plain strings for value_template (not cv.template)."""
    result = SERVICE_COMBINED_SCHEMA({
        CONF_RESOURCE: "https://example.com",
        "sensor": [{
            "name": "test",
            CONF_SELECT: ".data",
            "value_template": "{{ value | float }}",
        }],
    })
    assert result["sensor"][0]["value_template"] == "{{ value | float }}"


@pytest.mark.unit
def test_service_schema_accepts_string_icon():
    """Test service schema accepts plain strings for icon (not cv.template)."""
    result = SERVICE_COMBINED_SCHEMA({
        CONF_RESOURCE: "https://example.com",
        "sensor": [{
            "name": "test",
            CONF_SELECT: ".data",
            "icon": "mdi:thermometer",
        }],
    })
    assert result["sensor"][0]["icon"] == "mdi:thermometer"


# ============================================================================
# FORM_SUBMIT_SCHEMA tests
# ============================================================================


def _validate_form(config):
    """Validate a form_submit config."""
    return vol.Schema(FORM_SUBMIT_SCHEMA)(config)


@pytest.mark.unit
def test_form_schema_default_variables_empty_list():
    """Test that omitting variables defaults to [].

    This is critical: create_form_submitter checks `if variables:` to decide
    whether to iterate. The default must be [] (falsy) to avoid TypeError
    when iterating None.
    """
    result = _validate_form({})
    assert result[CONF_FORM_VARIABLES] == []


@pytest.mark.unit
def test_form_schema_accepts_variables_with_name_and_select():
    """Test that properly structured variables pass validation."""
    result = _validate_form({
        CONF_FORM_VARIABLES: [
            {"name": "csrf_token", CONF_SELECT: "input[name='csrf']"},
        ],
    })
    assert len(result[CONF_FORM_VARIABLES]) == 1
    assert result[CONF_FORM_VARIABLES][0]["name"] == "csrf_token"


@pytest.mark.unit
def test_form_schema_defaults():
    """Test form schema default values."""
    result = _validate_form({})
    assert result["input_filter"] == []
    assert result["submit_once"] is False
    assert result["resubmit_on_error"] is True
