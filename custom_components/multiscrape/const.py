import datetime

DEFAULT_NAME = "Multiscrape Sensor"
DEFAULT_VERIFY_SSL = True
DEFAULT_FORCE_UPDATE = False
DEFAULT_TIMEOUT = 10
DEFAULT_PARSER = "lxml"
DEFAULT_SCAN_INTERVAL = datetime.timedelta(seconds=30)
METHODS = ["POST", "GET", "PUT"]
DEFAULT_METHOD = "GET"

CONF_SELECTORS = "selectors"

CONF_PARSER = "parser"

CONF_ATTR = "attribute"
CONF_SELECT = "select"
CONF_INDEX = "index"

CONF_SELECTORS = "selectors"
