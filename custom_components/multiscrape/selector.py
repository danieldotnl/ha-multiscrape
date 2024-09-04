"""Abstraction of the CSS selectors defined in the config."""
from collections import namedtuple

from homeassistant.const import CONF_VALUE_TEMPLATE

from .const import (CONF_ATTR, CONF_EXTRACT, CONF_ON_ERROR,
                    CONF_ON_ERROR_DEFAULT, CONF_ON_ERROR_LOG,
                    CONF_ON_ERROR_VALUE, CONF_SELECT, CONF_SELECT_LIST,
                    DEFAULT_ON_ERROR_LOG, DEFAULT_ON_ERROR_VALUE)


class Selector:
    """Implementation of a Selector handling the css selectors from the config."""

    def __init__(self, hass, conf):
        """Initialize a Selector."""
        self.select_template = conf.get(CONF_SELECT)
        if self.select_template and self.select_template.hass is None:
            self.select_template.hass = hass

        self.select_list_template = conf.get(CONF_SELECT_LIST)
        if self.select_list_template and self.select_list_template.hass is None:
            self.select_list_template.hass = hass

        self.attribute = conf.get(CONF_ATTR)
        self.value_template = conf.get(CONF_VALUE_TEMPLATE)
        if self.value_template and self.value_template.hass is None:
            self.value_template.hass = hass

        self.extract = conf.get(CONF_EXTRACT)
        self.on_error = self.create_on_error(conf.get(CONF_ON_ERROR), hass)

        if (
            not self.select_template
            and not self.select_list_template
            and not self.value_template
        ):
            raise ValueError(
                "Selector error: either select, select_list or a value_template should be provided."
            )

    def create_on_error(self, conf, hass):
        """Determine from config what to do in case of scrape errors."""
        On_Error = namedtuple(
            "On_Error",
            f"{CONF_ON_ERROR_LOG} {CONF_ON_ERROR_VALUE} {CONF_ON_ERROR_DEFAULT}",
        )

        if not conf:
            return On_Error(DEFAULT_ON_ERROR_LOG, DEFAULT_ON_ERROR_VALUE, None)

        log = conf.get(CONF_ON_ERROR_LOG, DEFAULT_ON_ERROR_LOG)
        value = conf.get(CONF_ON_ERROR_VALUE, DEFAULT_ON_ERROR_VALUE)
        default_template = conf.get(CONF_ON_ERROR_DEFAULT)
        if default_template is not None:
            default_template.hass = hass

        return On_Error(log, value, default_template)

    @property
    def is_list(self):
        """Determine whether this selector is a list selector."""
        return self.select_list_template is not None

    @property
    def element(self):
        """Render the select template and return the CSS selector for a single element."""
        return self.select_template.async_render(parse_result=True)

    @property
    def list(self):
        """Render the select template and return the CSS selector for a list of elements."""
        return self.select_list_template.async_render(parse_result=True)

    @property
    def just_value(self):
        """Determine if this selector define a static value and no select is required."""
        return not self.select_list_template and not self.select_template

    @property
    def on_error_default(self):
        """Return the default on_error value in case as defined in the config."""
        return self.on_error.default.async_render(parse_result=True)
