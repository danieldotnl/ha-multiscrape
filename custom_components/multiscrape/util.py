"""Some utility functions."""
import logging

from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template

_LOGGER: logging.Logger = logging.getLogger(__name__)


def create_renderer(hass, value_template):
    """Create a template renderer based on value_template."""
    if value_template is None:
        return lambda variables={}, parse_result=None: None

    if not isinstance(value_template, Template):
        value_template = Template(value_template, hass)
    else:
        value_template.hass = hass

    def _render(variables: dict = {}, parse_result=False):
        try:
            return value_template.async_render(variables, parse_result)
        except TemplateError:
            _LOGGER.exception(
                "Error rendering template: %s with variables %s", value_template, variables
            )
            raise

    return _render


def create_dict_renderer(hass, templates_dict):
    """Create template renderers for a dictionary with value_templates."""
    if templates_dict is None:
        return lambda variables={}, parse_result=None: {}

    # Create a copy of the templates_dict to avoid modification of the original
    templates_dict = templates_dict.copy()
    for item in templates_dict:
        templates_dict[item] = create_renderer(hass, templates_dict[item])

    def _render(variables: dict = {}, parse_result=False):
        return {
            item: templates_dict[item](variables, parse_result) for item in templates_dict
        }

    return _render
