"""ScraperRegistry for type-safe, reload-safe scraper lookup."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.const import Platform

_LOGGER = logging.getLogger(__name__)


@dataclass
class ScraperInstance:
    """Holds all data for a single scraper configuration."""

    scraper_id: str
    scraper: object
    coordinator: object
    platform_configs: dict[Platform, dict[str, dict]] = field(default_factory=dict)


class ScraperRegistry:
    """Registry for scraper instances, replacing index-based lookups."""

    def __init__(self):
        """Initialize an empty registry."""
        self._scrapers: dict[str, ScraperInstance] = {}

    def register(self, instance: ScraperInstance) -> None:
        """Register a scraper instance by its unique ID."""
        if instance.scraper_id in self._scrapers:
            raise ValueError(
                f"Scraper '{instance.scraper_id}' is already registered"
            )
        self._scrapers[instance.scraper_id] = instance
        _LOGGER.debug("Registered scraper: %s", instance.scraper_id)

    def get(self, scraper_id: str) -> ScraperInstance:
        """Get a scraper instance by its unique ID."""
        return self._scrapers[scraper_id]

    def get_all(self) -> list[ScraperInstance]:
        """Get all registered scraper instances."""
        return list(self._scrapers.values())

    def clear(self) -> None:
        """Remove all registered scrapers."""
        self._scrapers.clear()
