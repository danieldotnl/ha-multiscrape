"""The multiscrape component schemas."""
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.binary_sensor import \
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA
from homeassistant.components.binary_sensor import \
    DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.sensor import \
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import \
    STATE_CLASSES_SCHEMA as SENSOR_STATE_CLASSES_SCHEMA
from homeassistant.const import (CONF_AUTHENTICATION, CONF_DEVICE_CLASS,
                                 CONF_FORCE_UPDATE, CONF_HEADERS, CONF_ICON,
                                 CONF_METHOD, CONF_NAME, CONF_PARAMS,
                                 CONF_PASSWORD, CONF_PAYLOAD, CONF_RESOURCE,
                                 CONF_RESOURCE_TEMPLATE, CONF_SCAN_INTERVAL,
                                 CONF_TIMEOUT, CONF_UNIQUE_ID,
                                 CONF_UNIT_OF_MEASUREMENT, CONF_USERNAME,
                                 CONF_VALUE_TEMPLATE, CONF_VERIFY_SSL,
                                 HTTP_BASIC_AUTHENTICATION,
                                 HTTP_DIGEST_AUTHENTICATION)

from .const import (CONF_ATTR, CONF_FORM_INPUT, CONF_FORM_INPUT_FILTER,
                    CONF_FORM_RESUBMIT_ERROR, CONF_FORM_SELECT,
                    CONF_FORM_SUBMIT, CONF_FORM_SUBMIT_ONCE,
                    CONF_FORM_VARIABLES, CONF_LOG_RESPONSE, CONF_ON_ERROR,
                    CONF_ON_ERROR_DEFAULT, CONF_ON_ERROR_LOG,
                    CONF_ON_ERROR_VALUE, CONF_ON_ERROR_VALUE_DEFAULT,
                    CONF_ON_ERROR_VALUE_LAST, CONF_ON_ERROR_VALUE_NONE,
                    CONF_PARSER, CONF_PICTURE, CONF_SELECT, CONF_SELECT_LIST,
                    CONF_SENSOR_ATTRS, CONF_SEPARATOR, CONF_STATE_CLASS,
                    DEFAULT_BINARY_SENSOR_NAME, DEFAULT_BUTTON_NAME,
                    DEFAULT_FORCE_UPDATE, DEFAULT_METHOD, DEFAULT_PARSER,
                    DEFAULT_SENSOR_NAME, DEFAULT_SEPARATOR, DEFAULT_VERIFY_SSL,
                    DOMAIN, LOG_ERROR, LOG_LEVELS, METHODS)
from .scraper import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

HTTP_SCHEMA = {
    vol.Exclusive(CONF_RESOURCE, CONF_RESOURCE): cv.url,
    vol.Exclusive(CONF_RESOURCE_TEMPLATE, CONF_RESOURCE): cv.template,
    vol.Optional(CONF_AUTHENTICATION): vol.In(
        [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
    ),
    vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.template}),
    vol.Optional(CONF_PARAMS): vol.Schema({cv.string: cv.template}),
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(METHODS),
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PAYLOAD): cv.template,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
}

INTEGRATION_SCHEMA = {
    **HTTP_SCHEMA,
    vol.Optional(CONF_PARSER, default=DEFAULT_PARSER): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
    vol.Optional(CONF_LOG_RESPONSE, default=False): cv.boolean,
    vol.Optional(CONF_SEPARATOR, default=DEFAULT_SEPARATOR): cv.string,
}

ON_ERROR_SCHEMA = {
    vol.Optional(CONF_ON_ERROR_LOG, default=LOG_ERROR): vol.In(list(LOG_LEVELS.keys())),
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
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ON_ERROR): vol.Schema(ON_ERROR_SCHEMA),
}

FORM_HEADERS_MAPPING_SCHEMA = {vol.Required(CONF_NAME): cv.string, **SELECTOR_SCHEMA}

FORM_SUBMIT_SCHEMA = {
    **HTTP_SCHEMA,
    vol.Optional(CONF_FORM_SELECT): cv.string,
    vol.Optional(CONF_FORM_INPUT): vol.Schema({cv.string: cv.string}),
    vol.Optional(CONF_FORM_INPUT_FILTER, default=[]): cv.ensure_list,
    vol.Optional(CONF_FORM_SUBMIT_ONCE, default=False): cv.boolean,
    vol.Optional(CONF_FORM_RESUBMIT_ERROR, default=True): cv.boolean,
    vol.Optional(CONF_FORM_VARIABLES, default=[]): vol.All(
        cv.ensure_list, [vol.Schema(FORM_HEADERS_MAPPING_SCHEMA)]
    ),
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


def create_service_schema():
    """Create a schema without templates that render an output value."""
    # Templates are evaluated by home assistant when the service is triggered, so we make them a string and restore them afterwards.
    SERVICE_SELECTOR_SCHEMA = dict(SELECTOR_SCHEMA)
    SERVICE_SELECTOR_SCHEMA.update({vol.Optional(CONF_VALUE_TEMPLATE): cv.string})

    SERVICE_SENSOR_ATTRIBUTE_SCHEMA = {
        vol.Required(CONF_NAME): cv.string,
        **SERVICE_SELECTOR_SCHEMA,
    }

    SERVICE_SENSOR_SCHEMA = dict(SENSOR_SCHEMA)
    SERVICE_SENSOR_SCHEMA.update({vol.Optional(CONF_VALUE_TEMPLATE): cv.string})
    SERVICE_SENSOR_SCHEMA.update({vol.Optional(CONF_ICON): cv.string})
    SERVICE_SENSOR_SCHEMA.update(
        {
            vol.Optional(CONF_SENSOR_ATTRS): vol.All(
                cv.ensure_list, [vol.Schema(SERVICE_SENSOR_ATTRIBUTE_SCHEMA)]
            )
        }
    )

    SERVICE_BINARY_SENSOR_SCHEMA = dict(BINARY_SENSOR_SCHEMA)
    SERVICE_BINARY_SENSOR_SCHEMA.update({vol.Optional(CONF_VALUE_TEMPLATE): cv.string})
    SERVICE_BINARY_SENSOR_SCHEMA.update({vol.Optional(CONF_ICON): cv.string})
    SERVICE_BINARY_SENSOR_SCHEMA.update(
        {
            vol.Optional(CONF_SENSOR_ATTRS): vol.All(
                cv.ensure_list, [vol.Schema(SERVICE_SENSOR_ATTRIBUTE_SCHEMA)]
            )
        }
    )

    return vol.Schema(
        {
            **INTEGRATION_SCHEMA,
            vol.Optional(CONF_FORM_SUBMIT): vol.Schema(FORM_SUBMIT_SCHEMA),
            vol.Optional(SENSOR_DOMAIN): vol.All(
                cv.ensure_list, [vol.Schema(SERVICE_SENSOR_SCHEMA)]
            ),
            vol.Optional(BINARY_SENSOR_DOMAIN): vol.All(
                cv.ensure_list, [vol.Schema(SERVICE_BINARY_SENSOR_SCHEMA)]
            ),
            vol.Optional(BUTTON_DOMAIN): vol.All(
                cv.ensure_list, [vol.Schema(BUTTON_SCHEMA)]
            ),
        }
    )


SERVICE_COMBINED_SCHEMA = create_service_schema()
