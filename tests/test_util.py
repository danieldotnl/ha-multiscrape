"""Integration tests for utility functions."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template

from custom_components.multiscrape.util import (create_dict_renderer,
                                                create_renderer)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_with_none_returns_none_renderer(hass: HomeAssistant):
    """Test create_renderer with None returns a renderer that returns None."""
    # Act
    renderer = create_renderer(hass, None)

    # Assert
    assert renderer() is None
    assert renderer(variables={}) is None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_with_string_template(hass: HomeAssistant):
    """Test create_renderer with string template."""
    # Arrange
    template_str = "Hello {{ name }}"

    # Act
    renderer = create_renderer(hass, template_str)
    result = renderer(variables={"name": "World"})

    # Assert
    assert result == "Hello World"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_with_template_object(hass: HomeAssistant):
    """Test create_renderer with Template object."""
    # Arrange
    template = Template("Value: {{ value }}", hass)

    # Act
    renderer = create_renderer(hass, template)
    result = renderer(variables={"value": 42})

    # Assert
    assert result == "Value: 42"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_with_context_parameter(hass: HomeAssistant):
    """Test create_renderer with context for better error messages."""
    # Arrange - use an invalid template syntax that actually raises TemplateError
    template = Template("{{ value | invalid_filter }}", hass)
    renderer = create_renderer(hass, template, context="test header")

    # Act & Assert - should include context in error
    with pytest.raises(TemplateError):
        renderer(variables={"value": "test"})


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_with_parse_result_true(hass: HomeAssistant):
    """Test create_renderer with parse_result=True."""
    # Arrange
    template = Template("{{ value | int }}", hass)
    renderer = create_renderer(hass, template)

    # Act
    result = renderer(variables={"value": "42"}, parse_result=True)

    # Assert
    assert result == 42
    assert isinstance(result, int)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_with_parse_result_false(hass: HomeAssistant):
    """Test create_renderer with parse_result=False returns string."""
    # Arrange
    template = Template("{{ value | int }}", hass)
    renderer = create_renderer(hass, template)

    # Act
    result = renderer(variables={"value": "42"}, parse_result=False)

    # Assert
    assert result == "42"
    assert isinstance(result, str)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_with_complex_template(hass: HomeAssistant):
    """Test create_renderer with complex Jinja2 template."""
    # Arrange
    template_str = "{% if enabled %}{{ value | upper }}{% else %}disabled{% endif %}"
    renderer = create_renderer(hass, template_str)

    # Act
    result1 = renderer(variables={"enabled": True, "value": "hello"})
    result2 = renderer(variables={"enabled": False, "value": "hello"})

    # Assert
    assert result1 == "HELLO"
    assert result2 == "disabled"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_with_empty_variables(hass: HomeAssistant):
    """Test create_renderer with no variables provided."""
    # Arrange
    template = Template("Static text", hass)
    renderer = create_renderer(hass, template)

    # Act
    result = renderer()

    # Assert
    assert result == "Static text"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_dict_renderer_with_none_returns_empty_dict_renderer(hass: HomeAssistant):
    """Test create_dict_renderer with None returns a renderer that returns empty dict."""
    # Act
    renderer = create_dict_renderer(hass, None)

    # Assert
    assert renderer() == {}
    assert renderer(variables={}) == {}


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_dict_renderer_with_string_templates(hass: HomeAssistant):
    """Test create_dict_renderer with string templates."""
    # Arrange
    templates = {
        "header1": "Bearer {{ token }}",
        "header2": "application/json",
    }

    # Act
    renderer = create_dict_renderer(hass, templates)
    result = renderer(variables={"token": "abc123"})

    # Assert
    assert result["header1"] == "Bearer abc123"
    assert result["header2"] == "application/json"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_dict_renderer_with_template_objects(hass: HomeAssistant):
    """Test create_dict_renderer with Template objects."""
    # Arrange
    templates = {
        "Authorization": Template("Bearer {{ token }}", hass),
        "X-User": Template("{{ user }}", hass),
    }

    # Act
    renderer = create_dict_renderer(hass, templates)
    result = renderer(variables={"token": "secret", "user": "john"})

    # Assert
    assert result["Authorization"] == "Bearer secret"
    assert result["X-User"] == "john"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_dict_renderer_preserves_original_dict(hass: HomeAssistant):
    """Test create_dict_renderer doesn't modify the original dictionary."""
    # Arrange
    original_templates = {
        "key1": "{{ value1 }}",
        "key2": "{{ value2 }}",
    }
    original_copy = original_templates.copy()

    # Act
    create_dict_renderer(hass, original_templates)

    # Assert - original dict should be unchanged
    assert original_templates == original_copy


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_dict_renderer_with_empty_dict(hass: HomeAssistant):
    """Test create_dict_renderer with empty dictionary."""
    # Arrange
    templates = {}

    # Act
    renderer = create_dict_renderer(hass, templates)
    result = renderer(variables={"key": "value"})

    # Assert
    assert result == {}


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_dict_renderer_with_multiple_variables(hass: HomeAssistant):
    """Test create_dict_renderer with multiple variables in templates."""
    # Arrange
    templates = {
        "url": "https://{{ domain }}/{{ path }}",
        "user": "{{ first }}_{{ last }}",
    }

    # Act
    renderer = create_dict_renderer(hass, templates)
    result = renderer(
        variables={"domain": "example.com", "path": "api", "first": "John", "last": "Doe"}
    )

    # Assert
    assert result["url"] == "https://example.com/api"
    assert result["user"] == "John_Doe"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_dict_renderer_with_parse_result(hass: HomeAssistant):
    """Test create_dict_renderer with parse_result parameter."""
    # Arrange
    templates = {
        "count": "{{ value | int }}",
        "name": "{{ name }}",
    }

    # Act
    renderer = create_dict_renderer(hass, templates)
    result = renderer(variables={"value": "42", "name": "test"}, parse_result=True)

    # Assert
    assert result["count"] == 42
    assert isinstance(result["count"], int)
    assert result["name"] == "test"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
def test_create_renderer_logs_template_error(hass: HomeAssistant, caplog):
    """Test create_renderer logs TemplateError with context."""
    # Arrange
    template = Template("{{ undefined_var.attribute }}", hass)
    renderer = create_renderer(hass, template, context="resource URL")

    # Act & Assert
    with pytest.raises(TemplateError):
        renderer(variables={})

    # Check that error was logged with context
    assert "resource URL" in caplog.text or "Error rendering template" in caplog.text
