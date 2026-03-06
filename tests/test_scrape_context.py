"""Tests for ScrapeContext dataclass."""
import dataclasses

import pytest

from custom_components.multiscrape.scrape_context import ScrapeContext

# ============================================================================
# Construction Tests
# ============================================================================


@pytest.mark.unit
def test_empty_context():
    """Test ScrapeContext.empty() creates context with defaults."""
    ctx = ScrapeContext.empty()
    assert ctx.form_variables == {}
    assert ctx.current_value is None


@pytest.mark.unit
def test_context_with_form_variables():
    """Test ScrapeContext preserves form variables."""
    ctx = ScrapeContext(form_variables={"token": "abc123", "session": "xyz"})
    assert ctx.form_variables == {"token": "abc123", "session": "xyz"}
    assert ctx.current_value is None


@pytest.mark.unit
def test_context_with_current_value():
    """Test ScrapeContext can be constructed with a current value."""
    ctx = ScrapeContext(current_value="42")
    assert ctx.form_variables == {}
    assert ctx.current_value == "42"


# ============================================================================
# Immutability Tests
# ============================================================================


@pytest.mark.unit
def test_frozen_cannot_set_form_variables():
    """Test that ScrapeContext is frozen and fields cannot be mutated."""
    ctx = ScrapeContext(form_variables={"key": "value"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.form_variables = {"other": "thing"}


@pytest.mark.unit
def test_frozen_cannot_set_current_value():
    """Test that current_value cannot be mutated on a frozen context."""
    ctx = ScrapeContext()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.current_value = "new_value"


# ============================================================================
# with_current_value Tests
# ============================================================================


@pytest.mark.unit
def test_with_current_value_returns_new_instance():
    """Test with_current_value returns a new context, leaving original unchanged."""
    original = ScrapeContext(form_variables={"token": "abc"})
    updated = original.with_current_value("scraped_data")

    assert updated is not original
    assert original.current_value is None
    assert updated.current_value == "scraped_data"
    assert updated.form_variables == {"token": "abc"}


@pytest.mark.unit
def test_with_current_value_preserves_form_variables():
    """Test with_current_value copies form variables to the new instance."""
    form_vars = {"a": "1", "b": "2"}
    ctx = ScrapeContext(form_variables=form_vars).with_current_value("val")
    assert ctx.form_variables == {"a": "1", "b": "2"}


# ============================================================================
# to_template_variables Tests
# ============================================================================


@pytest.mark.unit
def test_to_template_variables_empty():
    """Test empty context produces empty dict."""
    assert ScrapeContext.empty().to_template_variables() == {}


@pytest.mark.unit
def test_to_template_variables_form_only():
    """Test context with form variables but no current value."""
    ctx = ScrapeContext(form_variables={"token": "abc", "user": "admin"})
    result = ctx.to_template_variables()
    assert result == {"token": "abc", "user": "admin"}


@pytest.mark.unit
def test_to_template_variables_with_current_value():
    """Test context with current value includes 'value' key."""
    ctx = ScrapeContext(
        form_variables={"token": "abc"},
        current_value="42",
    )
    result = ctx.to_template_variables()
    assert result == {"token": "abc", "value": "42"}


@pytest.mark.unit
def test_to_template_variables_current_value_overrides_form_variable():
    """Test that current_value wins when form variables also has a 'value' key."""
    ctx = ScrapeContext(
        form_variables={"value": "from_form"},
        current_value="from_scrape",
    )
    result = ctx.to_template_variables()
    assert result == {"value": "from_scrape"}


@pytest.mark.unit
def test_to_template_variables_no_value_key_when_none():
    """Test that 'value' key is NOT added when current_value is None."""
    ctx = ScrapeContext(form_variables={"token": "abc"})
    result = ctx.to_template_variables()
    assert "value" not in result


@pytest.mark.unit
def test_to_template_variables_returns_copy():
    """Test that modifying the returned dict does not affect the context."""
    ctx = ScrapeContext(form_variables={"token": "abc"})
    result = ctx.to_template_variables()
    result["injected"] = "hack"
    assert "injected" not in ctx.form_variables
