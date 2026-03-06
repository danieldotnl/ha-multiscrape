"""Typed context for variable passing during scrape operations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScrapeContext:
    """Immutable context carrying variables through the scrape pipeline.

    Replaces the untyped dict[str, Any] that was previously passed through
    the entire call chain. Being frozen prevents the mutation bug where
    variables["value"] was modified in-place.
    """

    form_variables: dict[str, Any] = field(default_factory=dict)
    current_value: Any = None

    def with_current_value(self, value: Any) -> ScrapeContext:
        """Return a new context with current_value set."""
        return ScrapeContext(
            form_variables=self.form_variables,
            current_value=value,
        )

    def to_template_variables(self) -> dict[str, Any]:
        """Convert to the flat dict that HA templates expect.

        Form variables are included first, then 'value' is added on top
        if current_value is set. This preserves backward compatibility
        with existing user templates.
        """
        result = dict(self.form_variables)
        if self.current_value is not None:
            result["value"] = self.current_value
        return result

    @staticmethod
    def empty() -> ScrapeContext:
        """Create an empty context."""
        return ScrapeContext()
