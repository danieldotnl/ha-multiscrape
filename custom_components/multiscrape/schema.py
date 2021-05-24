import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
from homeassistant.const import CONF_HEADERS
from homeassistant.const import CONF_METHOD
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_PAYLOAD
from homeassistant.const import CONF_RESOURCE
from homeassistant.const import CONF_RESOURCE_TEMPLATE
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.const import CONF_TIMEOUT
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_USERNAME
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.const import CONF_VERIFY_SSL

from .const import CONF_ATTR
from .const import CONF_INDEX
from .const import CONF_PARSER
from .const import CONF_SELECT
from .const import CONF_SELECTORS
from .const import DEFAULT_FORCE_UPDATE
from .const import DEFAULT_METHOD
from .const import DEFAULT_NAME
from .const import DEFAULT_PARSER
from .const import DEFAULT_TIMEOUT
from .const import DEFAULT_VERIFY_SSL
from .const import METHODS

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Exclusive(CONF_RESOURCE, CONF_RESOURCE): cv.url,
        vol.Exclusive(CONF_RESOURCE_TEMPLATE, CONF_RESOURCE): cv.template,
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(METHODS),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PAYLOAD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_PARSER, default=DEFAULT_PARSER): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
    }
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SELECT): cv.template,
        vol.Optional(CONF_ATTR): cv.string,
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SELECTORS): cv.schema_with_slug_keys(SENSOR_SCHEMA)}
)
