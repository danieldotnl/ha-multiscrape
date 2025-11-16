"""Unit tests for the Selector class."""

import pytest
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.multiscrape.const import (CONF_ATTR, CONF_EXTRACT,
                                                 CONF_ON_ERROR,
                                                 CONF_ON_ERROR_DEFAULT,
                                                 CONF_ON_ERROR_LOG,
                                                 CONF_ON_ERROR_VALUE,
                                                 CONF_SELECT, CONF_SELECT_LIST,
                                                 DEFAULT_ON_ERROR_LOG,
                                                 DEFAULT_ON_ERROR_VALUE)
from custom_components.multiscrape.selector import Selector


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_with_select_only(hass: HomeAssistant):
    """Test selector with only 'select' configuration."""
    # Arrange
    conf = {CONF_SELECT: Template(".test", hass)}

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.element == ".test"
    assert not selector.is_list
    assert not selector.just_value


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_with_select_list_only(hass: HomeAssistant):
    """Test selector with only 'select_list' configuration."""
    # Arrange
    conf = {CONF_SELECT_LIST: Template(".item", hass)}

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.list == ".item"
    assert selector.is_list
    assert not selector.just_value


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_with_value_template_only(hass: HomeAssistant):
    """Test selector with only 'value_template' (no select)."""
    # Arrange
    conf = {CONF_VALUE_TEMPLATE: Template("{{ 'test' }}", hass)}

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.just_value
    assert selector.value_template is not None


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_raises_error_without_any_selector(hass: HomeAssistant):
    """Test that Selector raises ValueError when no selector is provided."""
    # Arrange
    conf = {CONF_NAME: "test"}  # No select, select_list, or value_template

    # Act & Assert
    with pytest.raises(
        ValueError,
        match="either select, select_list or a value_template should be provided",
    ):
        Selector(hass, conf)


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_with_attribute(hass: HomeAssistant):
    """Test selector with attribute extraction."""
    # Arrange
    conf = {CONF_SELECT: Template(".link", hass), CONF_ATTR: "href"}

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.attribute == "href"


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_with_extract_type(hass: HomeAssistant):
    """Test selector with extract type specified."""
    # Arrange
    conf = {CONF_SELECT: Template(".content", hass), CONF_EXTRACT: "text"}

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.extract == "text"


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_default_on_error_configuration(hass: HomeAssistant):
    """Test selector with default on_error configuration (no config provided)."""
    # Arrange
    conf = {CONF_SELECT: Template(".test", hass)}

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.on_error.log == DEFAULT_ON_ERROR_LOG
    assert selector.on_error.value == DEFAULT_ON_ERROR_VALUE
    assert selector.on_error.default is None


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_custom_on_error_log(hass: HomeAssistant):
    """Test selector with custom on_error log level."""
    # Arrange
    conf = {
        CONF_SELECT: Template(".test", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_LOG: "error"},
    }

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.on_error.log == "error"
    assert selector.on_error.value == DEFAULT_ON_ERROR_VALUE


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_custom_on_error_value(hass: HomeAssistant):
    """Test selector with custom on_error value strategy."""
    # Arrange
    conf = {
        CONF_SELECT: Template(".test", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_VALUE: "none"},
    }

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.on_error.value == "none"
    assert selector.on_error.log == DEFAULT_ON_ERROR_LOG


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_on_error_default_template(hass: HomeAssistant):
    """Test selector with on_error default value template."""
    # Arrange
    default_template = Template("{{ 'fallback_value' }}", hass)
    conf = {
        CONF_SELECT: Template(".test", hass),
        CONF_ON_ERROR: {CONF_ON_ERROR_DEFAULT: default_template},
    }

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.on_error.default is not None
    assert selector.on_error_default == "fallback_value"


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_hass_assignment_to_templates(hass: HomeAssistant):
    """Test that hass is properly assigned to all templates."""
    # Arrange
    select_template = Template(".test", None)  # hass intentionally None
    value_template = Template("{{ 'value' }}", None)

    conf = {
        CONF_SELECT: select_template,
        CONF_VALUE_TEMPLATE: value_template,
    }

    # Act
    selector = Selector(hass, conf)

    # Assert - hass should be assigned to templates
    assert selector.select_template.hass is not None
    assert selector.value_template.hass is not None


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_selector_with_all_configurations(hass: HomeAssistant):
    """Test selector with all possible configurations."""
    # Arrange
    conf = {
        CONF_NAME: "comprehensive_test",
        CONF_SELECT: Template(".content", hass),
        CONF_VALUE_TEMPLATE: Template("{{ value }}", hass),
        CONF_ATTR: "data-value",
        CONF_EXTRACT: "content",
        CONF_ON_ERROR: {
            CONF_ON_ERROR_LOG: "warning",
            CONF_ON_ERROR_VALUE: "last",
            CONF_ON_ERROR_DEFAULT: Template("{{ 'default' }}", hass),
        },
    }

    # Act
    selector = Selector(hass, conf)

    # Assert
    assert selector.name == "comprehensive_test"
    assert selector.element == ".content"
    assert selector.attribute == "data-value"
    assert selector.extract == "content"
    assert selector.value_template is not None
    assert selector.on_error.log == "warning"
    assert selector.on_error.value == "last"
    assert selector.on_error_default == "default"
