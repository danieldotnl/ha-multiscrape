"""The scraper component constants."""

DOMAIN = "multiscrape"

DEFAULT_METHOD = "GET"
DEFAULT_VERIFY_SSL = True
DEFAULT_FORCE_UPDATE = False

DEFAULT_BINARY_SENSOR_NAME = "Multiscrape Binary Sensor"
DEFAULT_SENSOR_NAME = "Multiscrape Sensor"
DEFAULT_BUTTON_NAME = "Multiscrape Refresh Button"

CONF_STATE_CLASS = "state_class"
CONF_ON_ERROR = "on_error"
CONF_ON_ERROR_LOG = "log"
CONF_ON_ERROR_VALUE = "value"
CONF_ON_ERROR_VALUE_LAST = "last"
CONF_ON_ERROR_VALUE_NONE = "none"
CONF_ON_ERROR_VALUE_DEFAULT = "default"
CONF_ON_ERROR_DEFAULT = "default"
CONF_PICTURE = "picture"
CONF_PARSER = "parser"
CONF_SELECT = "select"
CONF_SELECT_LIST = "select_list"
CONF_SEPARATOR = "list_separator"
CONF_ATTR = "attribute"
CONF_SENSOR_ATTRS = "attributes"
CONF_FORM_SUBMIT = "form_submit"
CONF_FORM_SELECT = "select"
CONF_FORM_INPUT = "input"
CONF_FORM_INPUT_FILTER = "input_filter"
CONF_FORM_SUBMIT_ONCE = "submit_once"
CONF_FORM_RESUBMIT_ERROR = "resubmit_on_error"
CONF_FORM_VARIABLES = "variables"
CONF_LOG_RESPONSE = "log_response"
CONF_EXTRACT = "extract"
EXTRACT_OPTIONS = ["text", "content", "tag"]
DEFAULT_PARSER = "lxml"
DEFAULT_EXTRACT = "text"

CONF_FIELDS = "fields"

SCRAPER_IDX = "scraper_idx"
PLATFORM_IDX = "platform_idx"

COORDINATOR = "coordinator"
SCRAPER = "scraper"

SCRAPER_DATA = "scraper"

METHODS = ["POST", "GET", "post", "get"]
DEFAULT_SEPARATOR = ","

LOG_ERROR = "error"
LOG_WARNING = "warning"
LOG_INFO = "info"
LOG_FALSE = False
LOG_LEVELS = {
    LOG_INFO: 20,
    LOG_WARNING: 30,
    LOG_ERROR: 40,
    LOG_FALSE: False,
    "false": False,
    "False": False,
}


DEFAULT_ON_ERROR_LOG = LOG_ERROR
DEFAULT_ON_ERROR_VALUE = CONF_ON_ERROR_VALUE_NONE
