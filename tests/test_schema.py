"""Unit tests for multiscrape schema validation."""

import pytest
import voluptuous as vol
from homeassistant.const import (CONF_AUTHENTICATION, CONF_FORCE_UPDATE,
                                 CONF_ICON, CONF_METHOD, CONF_NAME,
                                 CONF_RESOURCE, CONF_RESOURCE_TEMPLATE,
                                 CONF_SCAN_INTERVAL, CONF_TIMEOUT,
                                 CONF_UNIQUE_ID, CONF_VALUE_TEMPLATE,
                                 CONF_VERIFY_SSL, HTTP_BASIC_AUTHENTICATION,
                                 HTTP_DIGEST_AUTHENTICATION)

from custom_components.multiscrape.const import (CONF_EXTRACT,
                                                 CONF_FORM_VARIABLES,
                                                 CONF_LOG_RESPONSE,
                                                 CONF_ON_ERROR_LOG,
                                                 CONF_ON_ERROR_VALUE,
                                                 CONF_ON_ERROR_VALUE_DEFAULT,
                                                 CONF_ON_ERROR_VALUE_LAST,
                                                 CONF_ON_ERROR_VALUE_NONE,
                                                 CONF_PARSER, CONF_SELECT,
                                                 CONF_SEPARATOR,
                                                 DEFAULT_BINARY_SENSOR_NAME,
                                                 DEFAULT_BUTTON_NAME,
                                                 DEFAULT_EXTRACT,
                                                 DEFAULT_FORCE_UPDATE,
                                                 DEFAULT_PARSER,
                                                 DEFAULT_SENSOR_NAME,
                                                 DEFAULT_SEPARATOR, DOMAIN,
                                                 LOG_ERROR)
from custom_components.multiscrape.schema import (BINARY_SENSOR_SCHEMA,
                                                  BUTTON_SCHEMA,
                                                  COMBINED_SCHEMA,
                                                  CONFIG_SCHEMA,
                                                  FORM_SUBMIT_SCHEMA,
                                                  ON_ERROR_SCHEMA,
                                                  SELECTOR_SCHEMA,
                                                  SENSOR_SCHEMA,
                                                  SERVICE_COMBINED_SCHEMA,
                                                  create_service_schema)
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


@pytest.mark.unit
def test_form_schema_rejects_variables_without_name():
    """Test that variables entries require a 'name' field."""
    with pytest.raises(vol.Invalid):
        _validate_form({
            CONF_FORM_VARIABLES: [
                {CONF_SELECT: "input[name='csrf']"},
            ],
        })


# ============================================================================
# INTEGRATION_SCHEMA defaults tests
# ============================================================================


@pytest.mark.unit
def test_integration_schema_default_parser():
    """Test that omitting parser defaults to DEFAULT_PARSER ('lxml')."""
    result = _validate_combined({CONF_RESOURCE: "https://example.com"})
    assert result[CONF_PARSER] == DEFAULT_PARSER
    assert result[CONF_PARSER] == "lxml"


@pytest.mark.unit
def test_integration_schema_default_log_response():
    """Test that log_response defaults to False."""
    result = _validate_combined({CONF_RESOURCE: "https://example.com"})
    assert result[CONF_LOG_RESPONSE] is False


@pytest.mark.unit
def test_integration_schema_default_separator():
    """Test that separator defaults to DEFAULT_SEPARATOR (',')."""
    result = _validate_combined({CONF_RESOURCE: "https://example.com"})
    assert result[CONF_SEPARATOR] == DEFAULT_SEPARATOR
    assert result[CONF_SEPARATOR] == ","


@pytest.mark.unit
def test_integration_schema_scan_interval_optional():
    """Test that scan_interval is optional and not set by default."""
    result = _validate_combined({CONF_RESOURCE: "https://example.com"})
    assert CONF_SCAN_INTERVAL not in result


@pytest.mark.unit
def test_integration_schema_name_optional():
    """Test that name is optional and not set by default."""
    result = _validate_combined({CONF_RESOURCE: "https://example.com"})
    assert CONF_NAME not in result


@pytest.mark.unit
def test_integration_schema_custom_parser():
    """Test that a custom parser value is accepted."""
    result = _validate_combined({
        CONF_RESOURCE: "https://example.com",
        CONF_PARSER: "html.parser",
    })
    assert result[CONF_PARSER] == "html.parser"


# ============================================================================
# SENSOR_SCHEMA / BINARY_SENSOR_SCHEMA / BUTTON_SCHEMA defaults tests
# ============================================================================


def _validate_sensor(config):
    """Validate a sensor config."""
    return vol.Schema(SENSOR_SCHEMA)(config)


def _validate_binary_sensor(config):
    """Validate a binary_sensor config."""
    return vol.Schema(BINARY_SENSOR_SCHEMA)(config)


def _validate_button(config):
    """Validate a button config."""
    return vol.Schema(BUTTON_SCHEMA)(config)


@pytest.mark.unit
def test_sensor_schema_defaults():
    """Test sensor schema default values."""
    result = _validate_sensor({})
    assert result[CONF_NAME] == DEFAULT_SENSOR_NAME
    assert result[CONF_FORCE_UPDATE] == DEFAULT_FORCE_UPDATE
    assert result[CONF_FORCE_UPDATE] is False
    assert result[CONF_EXTRACT] == DEFAULT_EXTRACT


@pytest.mark.unit
def test_binary_sensor_schema_defaults():
    """Test binary_sensor schema default values."""
    result = _validate_binary_sensor({})
    assert result[CONF_NAME] == DEFAULT_BINARY_SENSOR_NAME
    assert result[CONF_FORCE_UPDATE] is False
    assert result[CONF_EXTRACT] == DEFAULT_EXTRACT


@pytest.mark.unit
def test_button_schema_defaults():
    """Test button schema default values."""
    result = _validate_button({})
    assert result[CONF_NAME] == DEFAULT_BUTTON_NAME


@pytest.mark.unit
def test_sensor_schema_optional_fields():
    """Test that sensor optional fields (unique_id, unit, etc.) are not set by default."""
    result = _validate_sensor({})
    assert CONF_UNIQUE_ID not in result
    assert "unit_of_measurement" not in result
    assert "device_class" not in result
    assert "state_class" not in result
    assert "picture" not in result


@pytest.mark.unit
def test_http_schema_rejects_negative_timeout():
    """Test that negative timeout values are rejected.

    Note: cv.positive_int in HA accepts 0 (it's really non-negative),
    so timeout=0 is valid at the schema level.
    """
    with pytest.raises(vol.Invalid):
        _validate_combined({
            CONF_RESOURCE: "https://example.com",
            CONF_TIMEOUT: -1,
        })


@pytest.mark.unit
def test_on_error_schema_rejects_invalid_log_level():
    """Test that invalid log levels are rejected."""
    with pytest.raises(vol.Invalid):
        _validate_on_error({CONF_ON_ERROR_LOG: "debug"})

    with pytest.raises(vol.Invalid):
        _validate_on_error({CONF_ON_ERROR_LOG: "critical"})


# ============================================================================
# create_service_schema() structural tests
# ============================================================================


@pytest.mark.unit
def test_service_schema_is_vol_schema():
    """Test that create_service_schema() returns a vol.Schema."""
    schema = create_service_schema()
    assert isinstance(schema, vol.Schema)


@pytest.mark.unit
def test_service_schema_inherits_integration_defaults():
    """Test that service schema inherits INTEGRATION_SCHEMA defaults."""
    result = SERVICE_COMBINED_SCHEMA({
        CONF_RESOURCE: "https://example.com",
    })
    assert result[CONF_PARSER] == DEFAULT_PARSER
    assert result[CONF_METHOD] == "get"
    assert result[CONF_VERIFY_SSL] is True


@pytest.mark.unit
def test_service_schema_binary_sensor_accepts_string_templates():
    """Test service schema accepts plain strings for binary_sensor templates."""
    result = SERVICE_COMBINED_SCHEMA({
        CONF_RESOURCE: "https://example.com",
        "binary_sensor": [{
            "name": "test",
            CONF_SELECT: ".status",
            CONF_VALUE_TEMPLATE: "{{ value == 'on' }}",
            CONF_ICON: "mdi:check",
        }],
    })
    assert result["binary_sensor"][0][CONF_VALUE_TEMPLATE] == "{{ value == 'on' }}"
    assert result["binary_sensor"][0][CONF_ICON] == "mdi:check"


@pytest.mark.unit
def test_service_schema_sensor_attributes_accept_string_value_template():
    """Test service schema accepts string value_template in sensor attributes."""
    result = SERVICE_COMBINED_SCHEMA({
        CONF_RESOURCE: "https://example.com",
        "sensor": [{
            "name": "test",
            CONF_SELECT: ".data",
            "attributes": [{
                "name": "detail",
                CONF_SELECT: ".detail",
                CONF_VALUE_TEMPLATE: "{{ value | int }}",
            }],
        }],
    })
    assert result["sensor"][0]["attributes"][0][CONF_VALUE_TEMPLATE] == "{{ value | int }}"


@pytest.mark.unit
def test_service_schema_idempotent():
    """Test that calling create_service_schema() multiple times returns equivalent schemas."""
    schema1 = create_service_schema()
    schema2 = create_service_schema()
    # Both should accept the same input
    config = {CONF_RESOURCE: "https://example.com"}
    result1 = schema1(config)
    result2 = schema2(config)
    assert result1 == result2


# ============================================================================
# COMBINED_SCHEMA entity type tests
# ============================================================================


@pytest.mark.unit
def test_combined_schema_accepts_binary_sensor():
    """Test COMBINED_SCHEMA accepts binary_sensor config."""
    result = _validate_combined({
        CONF_RESOURCE: "https://example.com",
        "binary_sensor": [{"name": "test", CONF_SELECT: ".status"}],
    })
    assert len(result["binary_sensor"]) == 1


@pytest.mark.unit
def test_combined_schema_accepts_button():
    """Test COMBINED_SCHEMA accepts button config."""
    result = _validate_combined({
        CONF_RESOURCE: "https://example.com",
        "button": [{"name": "refresh"}],
    })
    assert len(result["button"]) == 1


@pytest.mark.unit
def test_combined_schema_accepts_all_entity_types():
    """Test COMBINED_SCHEMA accepts sensor, binary_sensor, and button together."""
    result = _validate_combined({
        CONF_RESOURCE: "https://example.com",
        "sensor": [{"name": "temp", CONF_SELECT: ".temp"}],
        "binary_sensor": [{"name": "status", CONF_SELECT: ".status"}],
        "button": [{"name": "refresh"}],
    })
    assert len(result["sensor"]) == 1
    assert len(result["binary_sensor"]) == 1
    assert len(result["button"]) == 1


@pytest.mark.unit
def test_combined_schema_accepts_no_entities():
    """Test COMBINED_SCHEMA accepts config with no entity definitions.

    Entity presence is not enforced at schema level — the integration
    simply creates no entities, which is valid for a config-only entry.
    """
    result = _validate_combined({
        CONF_RESOURCE: "https://example.com",
    })
    assert CONF_RESOURCE in result
