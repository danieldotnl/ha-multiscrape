"""Some utility functions."""
import logging

from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template

_LOGGER: logging.Logger = logging.getLogger(__name__)


def create_renderer(hass, value_template, context="", strict=False, log_content=True):
    """Create a template renderer based on value_template.

    Args:
        hass: Home Assistant instance
        value_template: Template string or Template object
        context: Optional context description for better error messages (e.g., "resource URL", "header value")
        strict: Raise on undefined variables instead of rendering them as an empty
            string. Use for values where a silently wrong result is worse than an error.
        log_content: Include the template and its variables in the error log. Disable
            for templates that handle credentials, to keep secrets out of the log.

    """
    if value_template is None:
        return lambda variables={}, parse_result=None: None

    if not isinstance(value_template, Template):
        value_template = Template(value_template, hass)
    else:
        value_template.hass = hass

    def _render(variables: dict = {}, parse_result=False):
        try:
            return value_template.async_render(variables, parse_result, strict=strict)
        except TemplateError:
            if log_content:
                _LOGGER.exception(
                    "Error rendering template%s: %s with variables %s",
                    f" in {context}" if context else "",
                    value_template,
                    variables,
                )
            else:
                _LOGGER.exception(
                    "Error rendering template%s (template and variables not logged "
                    "because they may contain secrets)",
                    f" in {context}" if context else "",
                )
            raise

    return _render


def create_dict_renderer(hass, templates_dict, context="", strict=False, log_content=True):
    """Create template renderers for a dictionary with value_templates.

    Args:
        hass: Home Assistant instance
        templates_dict: Dictionary with template strings or Template objects as values
        context: Optional context description for better error messages (e.g. "form input")
        strict: See create_renderer.
        log_content: See create_renderer.

    """
    if templates_dict is None:
        return lambda variables={}, parse_result=None: {}

    # Create a copy of the templates_dict to avoid modification of the original
    templates_dict = templates_dict.copy()
    for item in templates_dict:
        # Name the failing key in error messages; key names are config, not secrets.
        item_context = f"{context} '{item}'" if context else f"'{item}'"
        templates_dict[item] = create_renderer(
            hass, templates_dict[item], item_context, strict, log_content
        )

    def _render(variables: dict = {}, parse_result=False):
        return {
            item: templates_dict[item](variables, parse_result) for item in templates_dict
        }

    return _render
