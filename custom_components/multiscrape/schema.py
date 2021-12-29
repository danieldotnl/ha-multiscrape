"""The multiscrape component schemas."""
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import (
    STATE_CLASSES_SCHEMA as SENSOR_STATE_CLASSES_SCHEMA,
)
from homeassistant.const import CONF_AUTHENTICATION
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
from homeassistant.const import CONF_HEADERS
from homeassistant.const import CONF_ICON
from homeassistant.const import CONF_METHOD
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_PARAMS
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PAYLOAD
from homeassistant.const import CONF_RESOURCE
from homeassistant.const import CONF_RESOURCE_TEMPLATE
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.const import CONF_TIMEOUT
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_USERNAME
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.const import HTTP_BASIC_AUTHENTICATION
from homeassistant.const import HTTP_DIGEST_AUTHENTICATION

from .const import CONF_ATTR
from .const import CONF_FORM_INPUT
from .const import CONF_FORM_RESOURCE
from .const import CONF_FORM_RESUBMIT_ERROR
from .const import CONF_FORM_SELECT
from .const import CONF_FORM_SUBMIT
from .const import CONF_FORM_SUBMIT_ONCE
from .const import CONF_INDEX
from .const import CONF_ON_ERROR
from .const import CONF_ON_ERROR_DEFAULT
from .const import CONF_ON_ERROR_LOG
from .const import CONF_ON_ERROR_VALUE
from .const import CONF_ON_ERROR_VALUE_DEFAULT
from .const import CONF_ON_ERROR_VALUE_LAST
from .const import CONF_ON_ERROR_VALUE_NONE
from .const import CONF_PARSER
from .const import CONF_PICTURE
from .const import CONF_SELECT
from .const import CONF_SELECT_LIST
from .const import CONF_SENSOR_ATTRS
from .const import CONF_STATE_CLASS
from .const import DEFAULT_BINARY_SENSOR_NAME
from .const import DEFAULT_BUTTON_NAME
from .const import DEFAULT_FORCE_UPDATE
from .const import DEFAULT_METHOD
from .const import DEFAULT_PARSER
from .const import DEFAULT_SENSOR_NAME
from .const import DEFAULT_VERIFY_SSL
from .const import DOMAIN
from .const import LOG_ERROR
from .const import LOG_LEVELS
from .const import METHODS
from .scraper import DEFAULT_TIMEOUT

FORM_SUBMIT_SCHEMA = {
    vol.Optional(CONF_FORM_RESOURCE): cv.string,
    vol.Required(CONF_FORM_SELECT): cv.string,
    vol.Optional(CONF_FORM_INPUT): vol.Schema({cv.string: cv.string}),
    vol.Optional(CONF_FORM_SUBMIT_ONCE, default=False): cv.boolean,
    vol.Optional(CONF_FORM_RESUBMIT_ERROR, default=True): cv.boolean,
}

INTEGRATION_SCHEMA = {
    vol.Exclusive(CONF_RESOURCE, CONF_RESOURCE): cv.url,
    vol.Exclusive(CONF_RESOURCE_TEMPLATE, CONF_RESOURCE): cv.template,
    vol.Optional(CONF_AUTHENTICATION): vol.In(
        [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
    ),
    vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
    vol.Optional(CONF_PARAMS): vol.Schema({cv.string: cv.string}),
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(METHODS),
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PAYLOAD): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_PARSER, default=DEFAULT_PARSER): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
}

ON_ERROR_SCHEMA = {
    vol.Optional(CONF_ON_ERROR_LOG, default=LOG_ERROR): vol.In(
        [key for key in LOG_LEVELS.keys()]
    ),
    vol.Optional(CONF_ON_ERROR_VALUE, default=CONF_ON_ERROR_VALUE_NONE): vol.In(
        [
            CONF_ON_ERROR_VALUE_LAST,
            CONF_ON_ERROR_VALUE_NONE,
            CONF_ON_ERROR_VALUE_DEFAULT,
        ]
    ),
    vol.Optional(CONF_ON_ERROR_DEFAULT): cv.template,
}

SELECTOR_SCHEMA = {
    vol.Optional(CONF_SELECT): cv.template,
    vol.Optional(CONF_SELECT_LIST): cv.template,
    vol.Optional(CONF_ATTR): cv.string,
    vol.Optional(CONF_INDEX, default=0): cv.positive_int,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ON_ERROR): vol.Schema(ON_ERROR_SCHEMA),
}

SENSOR_ATTRIBUTE_SCHEMA = {vol.Required(CONF_NAME): cv.string, **SELECTOR_SCHEMA}

SENSOR_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_SENSOR_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_STATE_CLASS): SENSOR_STATE_CLASSES_SCHEMA,
    vol.Optional(CONF_ICON): cv.template,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Optional(CONF_PICTURE): cv.string,
    **SELECTOR_SCHEMA,
    vol.Optional(CONF_SENSOR_ATTRS): vol.All(
        cv.ensure_list, [vol.Schema(SENSOR_ATTRIBUTE_SCHEMA)]
    ),
}

BINARY_SENSOR_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_BINARY_SENSOR_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_ICON): cv.template,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Optional(CONF_PICTURE): cv.string,
    **SELECTOR_SCHEMA,
    vol.Optional(CONF_SENSOR_ATTRS): vol.All(
        cv.ensure_list, [vol.Schema(SENSOR_ATTRIBUTE_SCHEMA)]
    ),
}

BUTTON_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_BUTTON_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
}

COMBINED_SCHEMA = vol.Schema(
    {
        **INTEGRATION_SCHEMA,
        vol.Optional(CONF_FORM_SUBMIT): vol.Schema(FORM_SUBMIT_SCHEMA),
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(SENSOR_SCHEMA)]
        ),
        vol.Optional(BINARY_SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(BINARY_SENSOR_SCHEMA)]
        ),
        vol.Optional(BUTTON_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(BUTTON_SCHEMA)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [COMBINED_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)
