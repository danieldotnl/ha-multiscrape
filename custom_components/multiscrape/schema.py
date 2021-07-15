"""The multiscrape component schemas."""
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.rest.const import DEFAULT_FORCE_UPDATE
from homeassistant.components.rest.schema import RESOURCE_SCHEMA
from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.const import CONF_FORCE_UPDATE
from homeassistant.const import CONF_ICON
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.const import CONF_VALUE_TEMPLATE

from .const import CONF_ATTR
from .const import CONF_FORM_INPUT
from .const import CONF_FORM_RESOURCE
from .const import CONF_FORM_RESUBMIT_ERROR
from .const import CONF_FORM_SELECT
from .const import CONF_FORM_SUBMIT
from .const import CONF_FORM_SUBMIT_ONCE
from .const import CONF_INDEX
from .const import CONF_PARSER
from .const import CONF_SELECT
from .const import CONF_SENSOR_ATTRS
from .const import DEFAULT_BINARY_SENSOR_NAME
from .const import DEFAULT_PARSER
from .const import DEFAULT_SENSOR_NAME
from .const import DOMAIN

FORM_SUBMIT_SCHEMA = {
    vol.Optional(CONF_FORM_RESOURCE): cv.string,
    vol.Required(CONF_FORM_SELECT): cv.string,
    vol.Optional(CONF_FORM_INPUT): vol.Schema({cv.string: cv.string}),
    vol.Optional(CONF_FORM_SUBMIT_ONCE, default=False): cv.boolean,
    vol.Optional(CONF_FORM_RESUBMIT_ERROR, default=True): cv.boolean,
}

RESOURCE_SCHEMA.update({vol.Optional(CONF_PARSER, default=DEFAULT_PARSER): cv.string})

SENSOR_ATTRIBUTE_SCHEMA = {
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_SELECT): cv.template,
    vol.Optional(CONF_ATTR): cv.string,
    vol.Optional(CONF_INDEX, default=0): cv.positive_int,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
}

SENSOR_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_SENSOR_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_ICON): cv.template,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Required(CONF_SELECT): cv.template,
    vol.Optional(CONF_ATTR): cv.string,
    vol.Optional(CONF_INDEX, default=0): cv.positive_int,
    vol.Optional(CONF_SENSOR_ATTRS): vol.All(
        cv.ensure_list, [vol.Schema(SENSOR_ATTRIBUTE_SCHEMA)]
    ),
}

BINARY_SENSOR_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_BINARY_SENSOR_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_ICON): cv.template,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Required(CONF_SELECT): cv.template,
    vol.Optional(CONF_ATTR): cv.string,
    vol.Optional(CONF_INDEX, default=0): cv.positive_int,
    vol.Optional(CONF_SENSOR_ATTRS): vol.All(
        cv.ensure_list, [vol.Schema(SENSOR_ATTRIBUTE_SCHEMA)]
    ),
}


COMBINED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        **RESOURCE_SCHEMA,
        vol.Optional(CONF_FORM_SUBMIT): vol.Schema(FORM_SUBMIT_SCHEMA),
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(SENSOR_SCHEMA)]
        ),
        vol.Optional(BINARY_SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(BINARY_SENSOR_SCHEMA)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [COMBINED_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)
