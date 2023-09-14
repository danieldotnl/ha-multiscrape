"""Some utility functions."""
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template


_LOGGER: logging.Logger = logging.getLogger(__name__)


def create_renderer(hass, value_template) -> Callable:
    """Create a renderer based on variable_template value."""
    if value_template is None:
        return lambda value=None, parse_result=None: value

    if not isinstance(value_template, Template):
        value_template = Template(value_template, hass)
    else:
        value_template.hass = hass

    def _render(value: Any = None, parse_result=False):
        _LOGGER.warning(
            "Executing _render with value: %s for template: %s", value, value_template
        )
        try:
            return value_template.async_render({"value": value}, parse_result)
        except TemplateError:
            _LOGGER.exception(
                "Error rendering template: %s with value %s", value_template, value
            )
            return value

    return _render


def create_dict_renderer(hass, templates_dict):
    """Create a dictionary of template renderers."""
    if templates_dict is None:
        return lambda value=None, parse_result=None: {}

    for item in templates_dict:
        templates_dict[item] = create_renderer(hass, templates_dict[item])

    def _render(value: Any = None, parse_result=False):
        return {
            item: templates_dict[item](value, parse_result) for item in templates_dict
        }

    return _render
