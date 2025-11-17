# Architecture Refactoring Plan

## Overview

This document outlines a comprehensive plan to refactor the ha-multiscrape architecture to address complexity issues, particularly around HTTP session management, form submission, variable handling, and parser organization.

**Current Status**: The integration works well but has accumulated complexity that makes it difficult to understand, maintain, and extend. The primary issues center around:

1. Dual HTTP wrapper instances with cookie/session juggling
2. Confusing variable system (form variables, template variables, selector variables)
3. Monolithic Scraper class doing too much
4. Backwards notification flow for error handling
5. Fragile index-based discovery mechanism
6. Missing strategy pattern for different content types (HTML vs JSON)

---

## Priority Fix #1: Unify HTTP Handling

### Current Problem

**Location**: `__init__.py:94-108`, `coordinator.py:41-96`

Currently, the integration creates **two separate HTTP wrapper instances**:

```python
# In __init__.py
if form_submit_config:
    form_http = create_http_wrapper(config_name, form_submit_config, hass, file_manager)
    form_submitter = create_form_submitter(
        config_name,
        form_submit_config,
        hass,
        form_http,  # First HTTP wrapper
        file_manager,
        parser,
    )

http = create_http_wrapper(config_name, conf, hass, file_manager)  # Second HTTP wrapper
```

This causes several issues:

1. **Cookie Management Chaos**: Cookies obtained from form login must be manually passed between objects
2. **Session State Loss**: Two separate httpx clients means no shared connection pooling or session state
3. **Confusing Control Flow**: Sometimes `ContentRequestManager.get_content()` returns form submit response, sometimes it makes a new request
4. **Resource URL Confusion**: Form submitter receives the main resource URL as a parameter but should use its own URL

**Current Flow Diagram**:

```
┌─────────────────────────────────────────────────────────────┐
│           ContentRequestManager.get_content()                │
│                                                              │
│  1. Render resource URL                                      │
│  2. If form_submitter exists:                                │
│     a. Call form_submitter.async_submit(resource)  ← Why?    │
│     b. Get result AND cookies back                           │
│     c. Extract form variables                                │
│     d. If result exists, return it (skip step 3)             │
│  3. Make HTTP request with http wrapper                      │
│     - Pass cookies from form submit                          │
│     - Pass form variables                                    │
│  4. Return response.text                                     │
└─────────────────────────────────────────────────────────────┘
         ↓                              ↓
┌──────────────────────┐      ┌─────────────────────┐
│   FormSubmitter      │      │    HttpWrapper      │
│   (has own HTTP)     │      │   (separate HTTP)   │
│                      │      │                     │
│  - Fetches form page │      │  - Makes requests   │
│  - Submits form      │      │  - No form context  │
│  - Returns cookies   │      │  - Receives cookies │
│  - Scrapes variables │      │    from outside     │
└──────────────────────┘      └─────────────────────┘
```

### Proposed Solution

**Create a unified `HttpSession` class** that manages authentication state, cookies, and all HTTP requests:

```python
# New file: custom_components/multiscrape/http_session.py

from dataclasses import dataclass, field
from typing import Any
import httpx
from homeassistant.core import HomeAssistant

@dataclass
class FormAuthConfig:
    """Configuration for form-based authentication."""
    resource: str
    select: str
    input: dict[str, Any]
    submit_once: bool = False
    resubmit_on_error: bool = False
    variables: list[dict] = field(default_factory=list)


class HttpSession:
    """Unified HTTP session manager with authentication support."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_name: str,
        file_manager: LoggingFileManager | None = None,
        auth_config: FormAuthConfig | None = None,
    ):
        """Initialize HTTP session."""
        self._hass = hass
        self._config_name = config_name
        self._file_manager = file_manager
        self._auth_config = auth_config

        # Single httpx client for all requests
        self._client: httpx.AsyncClient | None = None

        # Authentication state
        self._authenticated = False
        self._auth_variables: dict[str, Any] = {}
        self._session_valid = True

    async def ensure_authenticated(self) -> None:
        """Ensure session is authenticated, performing login if needed."""
        if not self._auth_config:
            return  # No auth needed

        if self._authenticated and self._session_valid:
            if self._auth_config.submit_once:
                return  # Already authenticated and submit_once is true

        await self._perform_form_login()

    async def _perform_form_login(self) -> None:
        """Perform form-based authentication."""
        _LOGGER.debug("%s # Performing form login", self._config_name)

        # 1. Fetch the form page
        form_response = await self._raw_request("GET", self._auth_config.resource)
        soup = BeautifulSoup(form_response.text, "lxml")

        # 2. Parse form and extract fields
        form_element = soup.select_one(self._auth_config.select)
        if not form_element:
            raise ValueError(f"Could not find form with selector: {self._auth_config.select}")

        form_data = self._extract_form_data(form_element)

        # 3. Merge with configured input values
        form_data.update(self._auth_config.input)

        # 4. Submit the form
        form_action = form_element.get("action", self._auth_config.resource)
        submit_response = await self._raw_request(
            "POST",
            form_action,
            data=form_data
        )

        # 5. Scrape variables from response if configured
        if self._auth_config.variables:
            self._auth_variables = self._scrape_variables(submit_response.text)

        self._authenticated = True
        self._session_valid = True
        _LOGGER.debug("%s # Form login successful", self._config_name)

    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Make an authenticated HTTP request."""
        await self.ensure_authenticated()

        # Merge auth variables into headers if needed
        if self._auth_variables:
            headers = kwargs.get("headers", {})
            # Render templates with auth variables
            rendered_headers = self._render_headers(headers, self._auth_variables)
            kwargs["headers"] = rendered_headers

        return await self._raw_request(method, url, **kwargs)

    async def _raw_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Make raw HTTP request using shared client."""
        if self._client is None:
            self._client = httpx.AsyncClient()

        response = await self._client.request(method, url, **kwargs)

        if self._file_manager:
            await self._log_request_response(method, url, response)

        return response

    def invalidate_session(self) -> None:
        """Mark session as invalid, forcing re-authentication on next request."""
        self._session_valid = False

    @property
    def auth_variables(self) -> dict[str, Any]:
        """Get variables scraped during authentication."""
        return self._auth_variables

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
```

**Updated ContentRequestManager** (now much simpler):

```python
# In coordinator.py

class ContentRequestManager:
    """Manages content retrieval using HTTP session."""

    def __init__(
        self,
        config_name: str,
        session: HttpSession,
        resource_renderer: Callable,
    ) -> None:
        """Initialize ContentRequestManager."""
        self._config_name = config_name
        self._session = session
        self._resource_renderer = resource_renderer

    async def get_content(self) -> str:
        """Retrieve content from the configured resource."""
        resource = self._resource_renderer()

        try:
            response = await self._session.request("GET", resource)
            return response.text
        except Exception as ex:
            _LOGGER.error(
                "%s # Failed to fetch content: %s",
                self._config_name,
                ex
            )
            # Invalidate session in case auth expired
            self._session.invalidate_session()
            raise

    @property
    def auth_variables(self) -> dict[str, Any]:
        """Get authentication variables."""
        return self._session.auth_variables
```

**Updated initialization** in `__init__.py`:

```python
# In __init__.py

async def _async_process_config(hass: HomeAssistant, config) -> bool:
    """Process scraper configuration."""

    for scraper_idx, conf in enumerate(config[DOMAIN]):
        config_name = conf.get(CONF_NAME) or f"Scraper_noname_{scraper_idx}"

        file_manager = await create_file_manager(hass, config_name, conf.get(CONF_LOG_RESPONSE))

        # Create auth config if form submit is configured
        auth_config = None
        if form_submit_config := conf.get(CONF_FORM_SUBMIT):
            auth_config = FormAuthConfig(
                resource=form_submit_config[CONF_RESOURCE],
                select=form_submit_config[CONF_FORM_SELECT],
                input=form_submit_config[CONF_FORM_INPUT],
                submit_once=form_submit_config.get(CONF_FORM_SUBMIT_ONCE, False),
                resubmit_on_error=form_submit_config.get(CONF_FORM_RESUBMIT_ERROR, False),
                variables=form_submit_config.get(CONF_FORM_VARIABLES, []),
            )

        # Single HTTP session for everything
        session = HttpSession(
            hass,
            config_name,
            file_manager,
            auth_config
        )

        scraper = create_scraper(config_name, conf, hass, file_manager)
        request_manager = create_content_request_manager(
            config_name,
            conf,
            hass,
            session  # Pass session instead of HTTP wrapper
        )
        coordinator = create_multiscrape_coordinator(
            config_name,
            conf,
            hass,
            request_manager,
            file_manager,
            scraper,
        )

        # Register cleanup
        async def cleanup_session():
            await session.close()

        coordinator.async_register_shutdown_callback(cleanup_session)
```

### Benefits

1. **Single HTTP Client**: One httpx client with proper connection pooling
2. **Natural Cookie Flow**: Cookies managed internally by httpx
3. **Clear Responsibility**: `HttpSession` handles ALL HTTP concerns
4. **Simpler Logic**: `ContentRequestManager` just fetches content
5. **Session Invalidation**: Clean pattern for re-authentication on errors
6. **Better Testing**: Can mock `HttpSession` easily

### Migration Path

1. Create new `http_session.py` module
2. Update `coordinator.py` to use `HttpSession`
3. Update `__init__.py` initialization
4. Deprecate old `FormSubmitter` and dual `HttpWrapper` pattern
5. Update tests to use new `HttpSession`
6. Remove old code after verification

---

## Priority Fix #2: Simplify Variable System

### Current Problem

**Location**: Multiple files - `coordinator.py`, `selector.py`, `entity.py`, `util.py`

Variables come from multiple sources and are mixed together without clear boundaries:

1. **Form Variables** - Scraped from login response (`coordinator.py:72`)
2. **Template Variables** - From Home Assistant template context
3. **Selector Variables** - Passed during scraping (`entity.py:145`)
4. **Resource Variables** - For URL template rendering

**Current Issues**:

```python
# In entity.py:145 - Mixing form variables into scraping
attr_value = self.scraper.scrape(
    attr_selector,
    self._name,
    name,
    variables=self.coordinator.form_variables  # ← Form variables passed everywhere
)

# In coordinator.py:233 - Property chain
@property
def form_variables(self):
    return self._request_manager.form_variables  # ← Law of Demeter violation

# In selector.py - Templates receive mixed variable context
value = selector.value_template.async_render(
    variables=variables,  # ← What's in here? Form vars? Template vars? Both?
    parse_result=True
)
```

**Problems**:

- No type safety - everything is `dict[str, Any]`
- Hard to track where variables come from
- Difficult to debug template rendering
- Variables leak across concerns (HTTP → Scraping → Templates)

### Proposed Solution

**Create a structured variable context system**:

```python
# New file: custom_components/multiscrape/context.py

from dataclasses import dataclass, field
from typing import Any
from homeassistant.helpers.template import Template

@dataclass(frozen=True)
class AuthContext:
    """Variables extracted during authentication."""
    variables: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get authentication variable."""
        return self.variables.get(key, default)


@dataclass(frozen=True)
class ScrapeContext:
    """Context available during scraping operations."""
    auth: AuthContext
    current_value: Any = None

    def to_template_variables(self) -> dict[str, Any]:
        """Convert to template variable dict."""
        result = {
            # Standard template variable
            "value": self.current_value,
        }

        # Add auth variables with prefix for clarity
        for key, val in self.auth.variables.items():
            result[f"auth_{key}"] = val

        return result


class VariableRenderer:
    """Renders templates with proper variable context."""

    def __init__(self, hass):
        """Initialize renderer."""
        self._hass = hass

    def render_template(
        self,
        template: Template,
        context: ScrapeContext,
        additional: dict[str, Any] | None = None
    ) -> Any:
        """Render template with structured context."""
        variables = context.to_template_variables()

        if additional:
            variables.update(additional)

        return template.async_render(variables=variables, parse_result=True)

    def render_dict(
        self,
        template_dict: dict[str, Template],
        context: ScrapeContext,
    ) -> dict[str, Any]:
        """Render a dictionary of templates (for headers, etc)."""
        return {
            key: self.render_template(tmpl, context)
            for key, tmpl in template_dict.items()
        }
```

**Updated Scraper**:

```python
# In scraper.py

class Scraper:
    """Class for handling the retrieval and scraping of data."""

    def __init__(
        self,
        config_name: str,
        hass: HomeAssistant,
        file_manager: LoggingFileManager | None,
        parser: str,
        separator: str,
    ):
        """Initialize scraper."""
        self._hass = hass
        self._config_name = config_name
        self._file_manager = file_manager
        self._parser = parser
        self._separator = separator
        self._renderer = VariableRenderer(hass)

        self._soup: BeautifulSoup | None = None
        self._data: str | None = None

    def scrape(
        self,
        selector: Selector,
        sensor: str,
        attribute: str | None = None,
        context: ScrapeContext | None = None
    ) -> Any:
        """Scrape value using selector with context."""
        context = context or ScrapeContext(auth=AuthContext())

        log_prefix = f"{self._config_name} # {sensor}"
        if attribute:
            log_prefix = f"{log_prefix} # {attribute}"

        # Handle value-only templates
        if selector.just_value:
            _LOGGER.debug("%s # Applying value_template only.", log_prefix)
            return self._renderer.render_template(
                selector.value_template,
                context
            )

        # Extract value from HTML/XML
        value = self._extract_value(selector, log_prefix)

        # Apply value template if configured
        if value is not None and selector.value_template is not None:
            _LOGGER.debug("%s # Applying value_template", log_prefix)
            # Update context with extracted value
            context = ScrapeContext(
                auth=context.auth,
                current_value=value
            )
            value = self._renderer.render_template(
                selector.value_template,
                context
            )

        return value
```

**Updated Entity**:

```python
# In entity.py

class MultiscrapeEntity(RestoreEntity):
    """Base entity with context-aware scraping."""

    def _update_attributes(self):
        """Update attributes using context."""
        if not self._attribute_selectors:
            return

        _LOGGER.debug(
            "%s # %s # Start scraping attributes",
            self.scraper.name,
            self._name,
        )

        # Create scrape context from coordinator
        auth_context = AuthContext(
            variables=self.coordinator.auth_variables
        )
        scrape_context = ScrapeContext(auth=auth_context)

        self.old_attributes = self._attr_extra_state_attributes
        self._attr_extra_state_attributes = {}

        for name, attr_selector in self._attribute_selectors.items():
            try:
                attr_value = self.scraper.scrape(
                    attr_selector,
                    self._name,
                    name,
                    context=scrape_context  # ← Clear, typed context
                )
                self._attr_extra_state_attributes[name] = attr_value
            except Exception as exception:
                self._handle_attribute_error(
                    name,
                    attr_selector,
                    exception
                )
```

**Updated HttpSession** (from Fix #1):

```python
# In http_session.py

class HttpSession:
    """HTTP session with structured variable support."""

    async def request(
        self,
        method: str,
        url: str,
        context: ScrapeContext | None = None,
        **kwargs
    ) -> httpx.Response:
        """Make request with context for header rendering."""
        await self.ensure_authenticated()

        if context and self._header_templates:
            # Render templated headers using context
            headers = self._renderer.render_dict(
                self._header_templates,
                context
            )
            kwargs["headers"] = {**kwargs.get("headers", {}), **headers}

        return await self._raw_request(method, url, **kwargs)
```

### Benefits

1. **Type Safety**: Clear types for different variable sources
2. **Explicit Context**: Know exactly what variables are available where
3. **Better Debugging**: Can inspect context objects
4. **Separation**: Auth variables stay in auth layer, scrape values in scrape layer
5. **Testability**: Easy to create mock contexts
6. **Template Clarity**: Variables are namespaced (`auth_token` vs `value`)

### Migration Path

1. Create `context.py` module
2. Update `Scraper.scrape()` to accept `ScrapeContext`
3. Update entities to create contexts
4. Update coordinator to expose `AuthContext`
5. Migrate templates to use namespaced variables
6. Update documentation with new variable naming

---

## Priority Fix #3: Refactor Scraper Class

### Current Problem

**Location**: `scraper.py:27-197`

The `Scraper` class has grown to 197 lines and mixes multiple concerns:

**Current responsibilities**:

1. Content storage (`_data`, `_soup`)
2. Content type detection (JSON vs HTML)
3. HTML parsing (BeautifulSoup)
4. CSS selector execution
5. Value extraction (text/content/tag)
6. List handling with separators
7. Template rendering
8. File logging

**Example of mixed concerns**:

```python
def scrape(self, selector, sensor, attribute=None, variables: dict = {}):
    """60+ line method doing everything."""

    # Template rendering (should be in VariableRenderer)
    if selector.just_value:
        result = selector.value_template.async_render_with_possible_json_value(...)
        return selector.value_template._parse_result(result)

    # Content type detection (should be in Parser)
    content_stripped = self._data.lstrip() if self._data else ""
    if content_stripped and content_stripped[0] in ["{", "["]:
        raise ValueError("JSON cannot be scraped...")

    # CSS selection (should be in Selector)
    if selector.is_list:
        tags = self._soup.select(selector.list)
    else:
        tag = self._soup.select_one(selector.element)

    # Value extraction (should be in Extractor)
    if selector.attribute is not None:
        value = tag[selector.attribute]
    else:
        value = self.extract_tag_value(tag, selector)

    # Template rendering again (should be in VariableRenderer)
    if value is not None and selector.value_template is not None:
        value = selector.value_template.async_render(...)
```

### Proposed Solution

**Split into focused classes using Strategy Pattern**:

```python
# New file: custom_components/multiscrape/parsers.py

from abc import ABC, abstractmethod
from typing import Any, Protocol
from bs4 import BeautifulSoup

class ParsedContent(Protocol):
    """Protocol for parsed content that can be queried."""

    def select_one(self, selector: str) -> Any:
        """Select single element."""
        ...

    def select(self, selector: str) -> list[Any]:
        """Select multiple elements."""
        ...


class ContentParser(ABC):
    """Base class for content parsers."""

    @abstractmethod
    async def parse(self, content: str) -> ParsedContent:
        """Parse content into queryable structure."""

    @abstractmethod
    def can_parse(self, content: str) -> bool:
        """Check if this parser can handle the content."""


class HtmlParser(ContentParser):
    """Parse HTML/XML content using BeautifulSoup."""

    def __init__(self, parser_name: str = "lxml"):
        """Initialize HTML parser."""
        self._parser_name = parser_name

    def can_parse(self, content: str) -> bool:
        """HTML parser handles anything that's not JSON."""
        content_stripped = content.lstrip() if content else ""
        if not content_stripped:
            return False
        return content_stripped[0] not in ["{", "["]

    async def parse(self, content: str, hass: HomeAssistant) -> BeautifulSoup:
        """Parse HTML content."""
        return await hass.async_add_executor_job(
            BeautifulSoup,
            content,
            self._parser_name
        )


class JsonParser(ContentParser):
    """Parse JSON content for jq-style queries."""

    def can_parse(self, content: str) -> bool:
        """Check if content is JSON."""
        content_stripped = content.lstrip() if content else ""
        if not content_stripped:
            return False
        return content_stripped[0] in ["{", "["]

    async def parse(self, content: str, hass: HomeAssistant) -> dict | list:
        """Parse JSON content."""
        import json
        return await hass.async_add_executor_job(json.loads, content)


class ParserFactory:
    """Factory for selecting appropriate parser."""

    def __init__(self, hass: HomeAssistant):
        """Initialize parser factory."""
        self._hass = hass
        self._parsers: list[ContentParser] = [
            JsonParser(),
            HtmlParser("lxml"),
        ]

    def get_parser(self, content: str) -> ContentParser:
        """Get appropriate parser for content."""
        for parser in self._parsers:
            if parser.can_parse(content):
                return parser
        raise ValueError("No parser available for content")

    async def parse(self, content: str) -> ParsedContent:
        """Parse content using appropriate parser."""
        parser = self.get_parser(content)
        return await parser.parse(content, self._hass)
```

```python
# New file: custom_components/multiscrape/extractors.py

from typing import Any
from bs4 import Tag

class ValueExtractor:
    """Extracts values from parsed content."""

    def __init__(self, separator: str = ","):
        """Initialize value extractor."""
        self._separator = separator

    def extract_single(
        self,
        element: Any,
        selector: Selector,
    ) -> Any:
        """Extract value from single element."""
        if selector.attribute is not None:
            return element[selector.attribute]
        return self._extract_tag_value(element, selector)

    def extract_list(
        self,
        elements: list[Any],
        selector: Selector,
    ) -> str:
        """Extract values from list of elements."""
        if selector.attribute is not None:
            values = [elem[selector.attribute] for elem in elements]
        else:
            values = [self._extract_tag_value(elem, selector) for elem in elements]

        return self._separator.join(values)

    def _extract_tag_value(self, tag: Tag, selector: Selector) -> str:
        """Extract value from HTML tag based on extract mode."""
        if tag.name in ("style", "script", "template"):
            return tag.string

        if selector.extract == "text":
            return tag.text
        elif selector.extract == "content":
            return ''.join(map(str, tag.contents))
        elif selector.extract == "tag":
            return str(tag)

        raise ValueError(f"Unknown extract mode: {selector.extract}")
```

```python
# Refactored scraper.py

from .parsers import ParserFactory
from .extractors import ValueExtractor
from .context import ScrapeContext, VariableRenderer

class Scraper:
    """Orchestrates parsing and value extraction."""

    def __init__(
        self,
        config_name: str,
        hass: HomeAssistant,
        file_manager: LoggingFileManager | None,
        parser_name: str,
        separator: str,
    ):
        """Initialize scraper."""
        self._config_name = config_name
        self._hass = hass
        self._file_manager = file_manager

        # Delegate to specialized components
        self._parser_factory = ParserFactory(hass)
        self._extractor = ValueExtractor(separator)
        self._renderer = VariableRenderer(hass)

        # State
        self._raw_content: str | None = None
        self._parsed_content: ParsedContent | None = None

    @property
    def name(self) -> str:
        """Get config name."""
        return self._config_name

    def reset(self) -> None:
        """Reset scraper state."""
        self._raw_content = None
        self._parsed_content = None

    async def set_content(self, content: str) -> None:
        """Parse and store content."""
        self._raw_content = content

        try:
            self._parsed_content = await self._parser_factory.parse(content)

            if self._file_manager:
                await self._log_parsed_content()

        except Exception as ex:
            self.reset()
            _LOGGER.error(
                "%s # Failed to parse content: %s",
                self._config_name,
                ex,
            )
            raise

    def scrape(
        self,
        selector: Selector,
        sensor: str,
        attribute: str | None = None,
        context: ScrapeContext | None = None,
    ) -> Any:
        """Scrape value using selector and context."""
        context = context or ScrapeContext(auth=AuthContext())
        log_prefix = self._make_log_prefix(sensor, attribute)

        # Handle template-only selectors
        if selector.just_value:
            _LOGGER.debug("%s # Using value template only", log_prefix)
            return self._renderer.render_template(
                selector.value_template,
                context
            )

        # Extract value from parsed content
        value = self._extract_value(selector, log_prefix)

        # Apply value template if present
        if value is not None and selector.value_template is not None:
            _LOGGER.debug("%s # Applying value template", log_prefix)
            context = ScrapeContext(
                auth=context.auth,
                current_value=value
            )
            value = self._renderer.render_template(
                selector.value_template,
                context
            )

        _LOGGER.debug(
            "%s # Final value: %s (type: %s)",
            log_prefix,
            value,
            type(value).__name__
        )

        return value

    def _extract_value(self, selector: Selector, log_prefix: str) -> Any:
        """Extract raw value from parsed content."""
        if self._parsed_content is None:
            raise ValueError("No content available to scrape")

        if selector.is_list:
            elements = self._parsed_content.select(selector.list)
            _LOGGER.debug("%s # Selected %d elements", log_prefix, len(elements))
            return self._extractor.extract_list(elements, selector)
        else:
            element = self._parsed_content.select_one(selector.element)
            if element is None:
                raise ValueError(f"Could not find element: {selector.element}")
            _LOGGER.debug("%s # Selected element: %s", log_prefix, element)
            return self._extractor.extract_single(element, selector)

    def _make_log_prefix(self, sensor: str, attribute: str | None) -> str:
        """Create log prefix for messages."""
        prefix = f"{self._config_name} # {sensor}"
        if attribute:
            prefix = f"{prefix} # {attribute}"
        return prefix

    async def _log_parsed_content(self) -> None:
        """Log parsed content to file."""
        if isinstance(self._parsed_content, BeautifulSoup):
            content = self._parsed_content.prettify()
        else:
            import json
            content = json.dumps(self._parsed_content, indent=2)

        await self._hass.async_add_executor_job(
            self._file_manager.write,
            "parsed_content.txt",
            content
        )
```

### Benefits

1. **Single Responsibility**: Each class has one clear job
2. **Strategy Pattern**: Easy to add new parsers (YAML, XML, etc.)
3. **Testability**: Can test parsers, extractors, renderers independently
4. **Maintainability**: Changes to parsing don't affect extraction
5. **Extensibility**: Adding JSON querying is now straightforward
6. **Clarity**: 197-line method becomes ~30 lines with clear delegation

### Migration Path

1. Create `parsers.py` module with `ContentParser` hierarchy
2. Create `extractors.py` module with `ValueExtractor`
3. Refactor `Scraper` to use new components
4. Update tests to test components separately
5. Add JSON parser implementation
6. Update documentation

---

## Priority Fix #4: Fix Notification Flow

### Current Problem

**Location**: `coordinator.py:164-166`, `coordinator.py:59-62`, entity classes

The notification flow for errors goes **backwards** through the dependency chain:

```
Entity (scraping fails)
    ↓
Coordinator.notify_scrape_exception()
    ↓
ContentRequestManager.notify_scrape_exception()
    ↓
FormSubmitter.notify_scrape_exception()
    ↓
Sets should_submit = True
```

**Code example**:

```python
# In coordinator.py:164
def notify_scrape_exception(self):
    """Notify the ContentRequestManager of a scrape exception so it can notify the FormSubmitter."""
    self._request_manager.notify_scrape_exception()

# In coordinator.py:59
def notify_scrape_exception(self):
    """Notify the form_submitter of an exception so it will re-submit next trigger."""
    if self._form_submitter:
        self._form_submitter.notify_scrape_exception()
```

**Problems**:

1. **Backwards dependency**: Lower layers shouldn't notify higher layers
2. **Tight coupling**: Coordinator knows about form submitter internals
3. **Hidden state changes**: `should_submit` is modified via chain of calls
4. **Hard to test**: Need to mock entire chain to test error handling
5. **Law of Demeter violation**: Coordinator reaches through request manager to form submitter

### Proposed Solution

**Use Event-Based Architecture** or **Session Validation**:

#### Option A: Event-Based (More Decoupled)

```python
# New file: custom_components/multiscrape/events.py

from dataclasses import dataclass
from typing import Callable
from enum import Enum

class EventType(Enum):
    """Event types for scraper lifecycle."""
    SCRAPE_FAILED = "scrape_failed"
    SCRAPE_SUCCEEDED = "scrape_succeeded"
    UPDATE_STARTED = "update_started"
    UPDATE_COMPLETED = "update_completed"


@dataclass
class ScraperEvent:
    """Event in scraper lifecycle."""
    type: EventType
    config_name: str
    error: Exception | None = None


class EventBus:
    """Simple event bus for scraper events."""

    def __init__(self):
        """Initialize event bus."""
        self._listeners: dict[EventType, list[Callable]] = {}

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def publish(self, event: ScraperEvent) -> None:
        """Publish an event to all subscribers."""
        if event.type in self._listeners:
            for callback in self._listeners[event.type]:
                callback(event)
```

**Updated HttpSession**:

```python
# In http_session.py

class HttpSession:
    """HTTP session with event-based auth management."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_name: str,
        event_bus: EventBus,
        file_manager: LoggingFileManager | None = None,
        auth_config: FormAuthConfig | None = None,
    ):
        """Initialize HTTP session."""
        self._hass = hass
        self._config_name = config_name
        self._event_bus = event_bus
        self._file_manager = file_manager
        self._auth_config = auth_config

        # Subscribe to scrape failures if using auth
        if self._auth_config and self._auth_config.resubmit_on_error:
            self._event_bus.subscribe(
                EventType.SCRAPE_FAILED,
                self._on_scrape_failed
            )

        self._authenticated = False
        self._session_valid = True

    def _on_scrape_failed(self, event: ScraperEvent) -> None:
        """Handle scrape failure event."""
        if event.config_name == self._config_name:
            _LOGGER.debug(
                "%s # Scrape failed, invalidating session for re-auth",
                self._config_name
            )
            self.invalidate_session()
```

**Updated Coordinator**:

```python
# In coordinator.py

class MultiscrapeDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator with event publishing."""

    def __init__(
        self,
        config_name: str,
        hass: HomeAssistant,
        event_bus: EventBus,
        request_manager: ContentRequestManager,
        file_manager: LoggingFileManager,
        scraper: Scraper,
        update_interval: timedelta | None,
    ):
        """Initialize coordinator."""
        self._config_name = config_name
        self._event_bus = event_bus
        self._request_manager = request_manager
        # ... rest of init

    async def _async_update_data(self):
        """Update data and publish events."""
        self._event_bus.publish(ScraperEvent(
            type=EventType.UPDATE_STARTED,
            config_name=self._config_name
        ))

        await self._prepare_new_run()

        try:
            response = await self._request_manager.get_content()
            await self._scraper.set_content(response)

            _LOGGER.debug(
                "%s # Data successfully refreshed",
                self._config_name,
            )

            self._event_bus.publish(ScraperEvent(
                type=EventType.SCRAPE_SUCCEEDED,
                config_name=self._config_name
            ))

            self._retry_count = 0

        except Exception as ex:
            _LOGGER.error(
                "%s # Updating failed: %s",
                self._config_name,
                ex,
            )

            self._event_bus.publish(ScraperEvent(
                type=EventType.SCRAPE_FAILED,
                config_name=self._config_name,
                error=ex
            ))

            self._scraper.reset()
            self.update_error = True
            self._handle_retry_logic()
```

#### Option B: Session Validation (Simpler)

```python
# In http_session.py

class HttpSession:
    """HTTP session with smart session validation."""

    def __init__(self, ...):
        """Initialize session."""
        self._last_auth_time: datetime | None = None
        self._auth_lifetime = timedelta(hours=1)  # Configurable
        self._consecutive_failures = 0

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make request with automatic re-auth on failure."""
        await self.ensure_authenticated()

        try:
            response = await self._raw_request(method, url, **kwargs)

            # Reset failure counter on success
            self._consecutive_failures = 0

            # Check for auth-related status codes
            if response.status_code in (401, 403):
                _LOGGER.warning(
                    "%s # Received %d, re-authenticating",
                    self._config_name,
                    response.status_code
                )
                await self._force_reauth()
                response = await self._raw_request(method, url, **kwargs)

            return response

        except Exception as ex:
            self._consecutive_failures += 1

            # Re-auth after multiple failures if configured
            if (self._consecutive_failures >= 3 and
                self._auth_config and
                self._auth_config.resubmit_on_error):
                _LOGGER.info(
                    "%s # Multiple failures, forcing re-auth",
                    self._config_name
                )
                await self._force_reauth()

            raise

    async def ensure_authenticated(self) -> None:
        """Ensure session is authenticated."""
        if not self._auth_config:
            return

        # Check if session is still valid
        if self._authenticated and self._session_valid:
            # Check if auth has expired
            if (self._last_auth_time and
                datetime.now() - self._last_auth_time > self._auth_lifetime):
                _LOGGER.debug(
                    "%s # Session expired, re-authenticating",
                    self._config_name
                )
                self._session_valid = False
            elif self._auth_config.submit_once:
                return

        if not self._session_valid:
            await self._perform_form_login()

    async def _force_reauth(self) -> None:
        """Force re-authentication."""
        self._session_valid = False
        self._authenticated = False
        await self.ensure_authenticated()
```

### Recommended Approach

**Use Option B (Session Validation)** for initial implementation:

**Pros**:

- Simpler to implement
- No new event infrastructure needed
- Self-contained logic in HttpSession
- Easier to understand and debug

**Cons**:

- Slightly more coupling (HttpSession knows about HTTP status codes)
- Less extensible for future event-based features

**Later migration to Option A** if needed for:

- Multiple subscribers to events
- More complex coordination logic
- Metrics/monitoring integration

### Benefits

1. **Natural Dependencies**: HttpSession manages its own state
2. **No Backwards Flow**: Coordinator doesn't reach into HTTP layer
3. **Self-Healing**: Automatic retry on auth failures
4. **Configurable**: Auth lifetime, failure thresholds
5. **Testable**: Can test session validation independently

### Migration Path

1. Implement session validation in `HttpSession`
2. Remove `notify_scrape_exception()` methods
3. Update coordinator to not call notification methods
4. Test automatic re-auth on 401/403
5. Add configuration for auth lifetime
6. Remove `should_submit` state management

---

## Priority Fix #5: Replace Index-Based Discovery

### Current Problem

**Location**: `__init__.py:121-142`, platform files

The current discovery mechanism uses **array indices** to connect scrapers with platforms:

```python
# In __init__.py:121-142
hass.data[DOMAIN][SCRAPER_DATA].append(
    {SCRAPER: scraper, COORDINATOR: coordinator}
)

for platform_domain in PLATFORMS:
    if platform_domain not in conf:
        continue

    for platform_conf in conf[platform_domain]:
        hass.data[DOMAIN][platform_domain].append(platform_conf)
        platform_idx = len(hass.data[DOMAIN][platform_domain]) - 1

        load = discovery.async_load_platform(
            hass,
            platform_domain,
            DOMAIN,
            {SCRAPER_IDX: scraper_idx, PLATFORM_IDX: platform_idx},  # ← Indices!
            config,
        )

# In platforms (sensor.py, binary_sensor.py, etc):
async def async_get_config_and_coordinator(hass, platform_domain, discovery_info):
    shared_data = hass.data[DOMAIN][SCRAPER_DATA][discovery_info[SCRAPER_IDX]]  # ← Array lookup
    conf = hass.data[DOMAIN][platform_domain][discovery_info[PLATFORM_IDX]]      # ← Array lookup
    coordinator = shared_data[COORDINATOR]
    scraper = shared_data[SCRAPER]
    return conf, coordinator, scraper
```

**Problems**:

1. **Fragile**: Indices can break if reload changes order
2. **No Type Safety**: Everything is `dict[str, Any]` and `list[Any]`
3. **Hard to Debug**: "Which scraper is index 2?" requires mental mapping
4. **Magic Keys**: `SCRAPER_IDX`, `PLATFORM_IDX`, `SCRAPER`, `COORDINATOR`
5. **Race Conditions**: What if platform loads before scraper appends?

### Proposed Solution

**Use structured data classes with unique IDs**:

```python
# New file: custom_components/multiscrape/registry.py

from dataclasses import dataclass, field
from typing import Any
from homeassistant.core import HomeAssistant
from .coordinator import MultiscrapeDataUpdateCoordinator
from .scraper import Scraper
from .http_session import HttpSession

@dataclass
class ScraperInstance:
    """A configured scraper instance."""
    id: str
    name: str
    coordinator: MultiscrapeDataUpdateCoordinator
    scraper: Scraper
    session: HttpSession
    config: dict[str, Any]

    @property
    def unique_id(self) -> str:
        """Get unique identifier."""
        return self.id


@dataclass
class PlatformConfig:
    """Configuration for a platform entity."""
    scraper_id: str
    config: dict[str, Any]
    unique_id: str


class ScraperRegistry:
    """Registry for scraper instances and platform configs."""

    def __init__(self):
        """Initialize registry."""
        self._scrapers: dict[str, ScraperInstance] = {}
        self._platform_configs: dict[str, list[PlatformConfig]] = {
            Platform.SENSOR: [],
            Platform.BINARY_SENSOR: [],
            Platform.BUTTON: [],
        }

    def register_scraper(self, instance: ScraperInstance) -> None:
        """Register a scraper instance."""
        if instance.id in self._scrapers:
            raise ValueError(f"Scraper {instance.id} already registered")
        self._scrapers[instance.id] = instance

    def get_scraper(self, scraper_id: str) -> ScraperInstance:
        """Get scraper by ID."""
        if scraper_id not in self._scrapers:
            raise ValueError(f"Scraper {scraper_id} not found")
        return self._scrapers[scraper_id]

    def register_platform_config(
        self,
        platform: Platform,
        scraper_id: str,
        config: dict[str, Any]
    ) -> str:
        """Register a platform configuration and return unique ID."""
        unique_id = f"{scraper_id}_{platform}_{len(self._platform_configs[platform])}"

        platform_config = PlatformConfig(
            scraper_id=scraper_id,
            config=config,
            unique_id=unique_id,
        )

        self._platform_configs[platform].append(platform_config)
        return unique_id

    def get_platform_config(self, platform: Platform, unique_id: str) -> PlatformConfig:
        """Get platform configuration by unique ID."""
        for config in self._platform_configs[platform]:
            if config.unique_id == unique_id:
                return config
        raise ValueError(f"Platform config {unique_id} not found")

    def get_all_platform_configs(self, platform: Platform) -> list[PlatformConfig]:
        """Get all configs for a platform."""
        return self._platform_configs[platform]

    async def async_shutdown(self) -> None:
        """Shutdown all scrapers."""
        for instance in self._scrapers.values():
            await instance.session.close()


def get_registry(hass: HomeAssistant) -> ScraperRegistry:
    """Get or create the scraper registry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if "registry" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["registry"] = ScraperRegistry()
    return hass.data[DOMAIN]["registry"]
```

**Updated initialization**:

```python
# In __init__.py

async def _async_process_config(hass: HomeAssistant, config) -> bool:
    """Process scraper configuration."""

    registry = get_registry(hass)
    load_tasks = []

    for scraper_idx, conf in enumerate(config[DOMAIN]):
        # Generate unique ID for scraper
        config_name = conf.get(CONF_NAME) or f"scraper_{scraper_idx}"
        scraper_id = f"{DOMAIN}_{config_name}".replace(" ", "_").lower()

        _LOGGER.debug("%s # Setting up scraper with ID: %s", config_name, scraper_id)

        file_manager = await create_file_manager(hass, config_name, conf.get(CONF_LOG_RESPONSE))

        # Create components
        event_bus = EventBus()
        auth_config = _create_auth_config(conf.get(CONF_FORM_SUBMIT))
        session = HttpSession(hass, config_name, event_bus, file_manager, auth_config)
        scraper = create_scraper(config_name, conf, hass, file_manager)
        request_manager = create_content_request_manager(config_name, conf, hass, session)
        coordinator = create_multiscrape_coordinator(
            config_name, conf, hass, event_bus, request_manager, file_manager, scraper
        )

        # Register scraper instance
        instance = ScraperInstance(
            id=scraper_id,
            name=config_name,
            coordinator=coordinator,
            scraper=scraper,
            session=session,
            config=conf,
        )
        registry.register_scraper(instance)

        await setup_config_services(hass, coordinator, config_name)

        # Register platform configs and load platforms
        for platform_domain in PLATFORMS:
            if platform_domain not in conf:
                continue

            for platform_conf in conf[platform_domain]:
                # Register config and get unique ID
                unique_id = registry.register_platform_config(
                    platform_domain,
                    scraper_id,
                    platform_conf
                )

                # Load platform with unique ID
                load = discovery.async_load_platform(
                    hass,
                    platform_domain,
                    DOMAIN,
                    {"unique_id": unique_id},  # ← Pass unique ID, not indices
                    config,
                )
                load_tasks.append(load)

    if load_tasks:
        await asyncio.gather(*load_tasks)

    return True
```

**Updated platform setup**:

```python
# In sensor.py (and similar for binary_sensor.py, button.py)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the multiscrape sensor."""
    if discovery_info is None:
        return

    registry = get_registry(hass)

    # Get platform config by unique ID
    unique_id = discovery_info["unique_id"]
    platform_config = registry.get_platform_config(Platform.SENSOR, unique_id)

    # Get scraper instance
    scraper_instance = registry.get_scraper(platform_config.scraper_id)

    # Create entity
    entity = MultiscrapeSensor(
        hass,
        scraper_instance.coordinator,
        scraper_instance.scraper,
        platform_config.config,
    )

    async_add_entities([entity])


# New helper function (replaces async_get_config_and_coordinator)
def get_scraper_for_platform(
    hass: HomeAssistant,
    platform: Platform,
    unique_id: str,
) -> tuple[dict[str, Any], MultiscrapeDataUpdateCoordinator, Scraper]:
    """Get scraper components for a platform entity."""
    registry = get_registry(hass)
    platform_config = registry.get_platform_config(platform, unique_id)
    scraper_instance = registry.get_scraper(platform_config.scraper_id)

    return (
        platform_config.config,
        scraper_instance.coordinator,
        scraper_instance.scraper,
    )
```

### Benefits

1. **Type Safety**: Dataclasses with proper types
2. **Debuggable**: Can inspect `registry._scrapers` to see all instances
3. **Unique IDs**: Proper identification instead of array indices
4. **Reload Safe**: IDs don't change when order changes
5. **Testable**: Can create registry with test data
6. **Extensible**: Easy to add more metadata to instances

### Migration Path

1. Create `registry.py` module
2. Update `__init__.py` to use registry
3. Update platform files to use registry
4. Test reload functionality
5. Remove old index-based constants
6. Update documentation

---

## Priority Fix #6: Extract Strategy Pattern for Parsers

### Current Problem

**Location**: `scraper.py:67-98`

Content type detection and parsing is mixed with scraping logic:

```python
async def set_content(self, content):
    """Set the content to be scraped."""
    self._data = content

    # Try to detect JSON more robustly
    content_stripped = content.lstrip() if content else ""
    if content_stripped and content_stripped[0] in ["{", "["]:
        _LOGGER.debug(
            "%s # Response seems to be json. Skip parsing with BeautifulSoup.",
            self._config_name,
        )
    else:
        try:
            _LOGGER.debug(
                "%s # Loading the content in BeautifulSoup.",
                self._config_name,
            )
            self._soup = await self._hass.async_add_executor_job(
                BeautifulSoup, self._data, self._parser
            )
```

**Then during scraping**:

```python
def scrape(self, selector, sensor, attribute=None, variables: dict = {}):
    # Check AGAIN if content is JSON
    content_stripped = self._data.lstrip() if self._data else ""
    if content_stripped and content_stripped[0] in ["{", "["]:
        raise ValueError(
            "JSON cannot be scraped. Please provide a value template to parse JSON response."
        )
```

**Problems**:

1. **Duplicate Detection**: JSON check happens twice
2. **No JSON Support**: JSON content requires template workaround
3. **Hard to Extend**: Adding YAML/XML support means modifying Scraper
4. **Mixed Concerns**: Parser selection in scraping logic
5. **Error Messages**: "JSON cannot be scraped" is a limitation, not a feature

### Proposed Solution

**Already covered in Priority Fix #3**, but here's the focused strategy pattern:

```python
# In parsers.py (expanded)

from abc import ABC, abstractmethod
from typing import Any, Protocol
from bs4 import BeautifulSoup
import json

class QueryResult:
    """Result of a query against parsed content."""

    def __init__(self, value: Any):
        """Initialize query result."""
        self._value = value

    @property
    def value(self) -> Any:
        """Get the result value."""
        return self._value

    def exists(self) -> bool:
        """Check if result exists (not None)."""
        return self._value is not None


class ParsedContent(Protocol):
    """Protocol for parsed content that can be queried."""

    def select_one(self, selector: str) -> QueryResult:
        """Select single element/value."""
        ...

    def select(self, selector: str) -> list[QueryResult]:
        """Select multiple elements/values."""
        ...


class HtmlContent(ParsedContent):
    """Parsed HTML content."""

    def __init__(self, soup: BeautifulSoup):
        """Initialize with BeautifulSoup."""
        self._soup = soup

    def select_one(self, selector: str) -> QueryResult:
        """Select using CSS selector."""
        element = self._soup.select_one(selector)
        return QueryResult(element)

    def select(self, selector: str) -> list[QueryResult]:
        """Select multiple using CSS selector."""
        elements = self._soup.select(selector)
        return [QueryResult(elem) for elem in elements]


class JsonContent(ParsedContent):
    """Parsed JSON content with JSONPath support."""

    def __init__(self, data: dict | list):
        """Initialize with parsed JSON."""
        self._data = data

    def select_one(self, selector: str) -> QueryResult:
        """Select using JSONPath selector."""
        # Simple implementation - could use jsonpath_ng for complex queries
        result = self._simple_jsonpath(selector)
        return QueryResult(result[0] if result else None)

    def select(self, selector: str) -> list[QueryResult]:
        """Select multiple using JSONPath."""
        results = self._simple_jsonpath(selector)
        return [QueryResult(r) for r in results]

    def _simple_jsonpath(self, path: str) -> list[Any]:
        """Simple JSONPath implementation for basic queries."""
        # Examples:
        # "$.data.items" -> root.data.items
        # "$[0].name" -> root[0].name

        if path.startswith("$."):
            path = path[2:]
        elif path.startswith("$["):
            path = path[1:]

        parts = path.replace("[", ".").replace("]", "").split(".")

        current = [self._data]
        for part in parts:
            if not part:
                continue

            next_level = []
            for item in current:
                if isinstance(item, dict) and part in item:
                    next_level.append(item[part])
                elif isinstance(item, list):
                    try:
                        idx = int(part)
                        if 0 <= idx < len(item):
                            next_level.append(item[idx])
                    except ValueError:
                        # Not an index, try as key in all list items
                        for subitem in item:
                            if isinstance(subitem, dict) and part in subitem:
                                next_level.append(subitem[part])

            current = next_level

        return current


class ContentParser(ABC):
    """Base class for content parsers."""

    @abstractmethod
    async def parse(self, content: str, hass: HomeAssistant) -> ParsedContent:
        """Parse content into queryable structure."""

    @abstractmethod
    def can_parse(self, content: str) -> bool:
        """Check if this parser can handle the content."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get parser name for logging."""


class HtmlParser(ContentParser):
    """Parse HTML/XML content using BeautifulSoup."""

    def __init__(self, parser_name: str = "lxml"):
        """Initialize HTML parser."""
        self._parser_name = parser_name

    @property
    def name(self) -> str:
        """Get parser name."""
        return f"html:{self._parser_name}"

    def can_parse(self, content: str) -> bool:
        """HTML parser handles anything that's not JSON."""
        content_stripped = content.lstrip() if content else ""
        if not content_stripped:
            return False
        return content_stripped[0] not in ["{", "["]

    async def parse(self, content: str, hass: HomeAssistant) -> HtmlContent:
        """Parse HTML content."""
        soup = await hass.async_add_executor_job(
            BeautifulSoup,
            content,
            self._parser_name
        )
        return HtmlContent(soup)


class JsonParser(ContentParser):
    """Parse JSON content for JSONPath queries."""

    @property
    def name(self) -> str:
        """Get parser name."""
        return "json"

    def can_parse(self, content: str) -> bool:
        """Check if content is JSON."""
        content_stripped = content.lstrip() if content else ""
        if not content_stripped:
            return False
        return content_stripped[0] in ["{", "["]

    async def parse(self, content: str, hass: HomeAssistant) -> JsonContent:
        """Parse JSON content."""
        data = await hass.async_add_executor_job(json.loads, content)
        return JsonContent(data)


class ParserFactory:
    """Factory for selecting appropriate parser."""

    def __init__(self, hass: HomeAssistant, default_parser: str = "lxml"):
        """Initialize parser factory."""
        self._hass = hass
        self._parsers: list[ContentParser] = [
            JsonParser(),
            HtmlParser(default_parser),
        ]

    def register_parser(self, parser: ContentParser) -> None:
        """Register a custom parser."""
        self._parsers.insert(0, parser)  # Custom parsers take precedence

    def get_parser(self, content: str) -> ContentParser:
        """Get appropriate parser for content."""
        for parser in self._parsers:
            if parser.can_parse(content):
                _LOGGER.debug("Selected parser: %s", parser.name)
                return parser
        raise ValueError("No parser available for content")

    async def parse(self, content: str) -> ParsedContent:
        """Parse content using appropriate parser."""
        parser = self.get_parser(content)
        _LOGGER.debug("Parsing content with: %s", parser.name)
        return await parser.parse(content, self._hass)
```

**Updated Selector** to support both CSS and JSONPath:

```python
# In selector.py

from dataclasses import dataclass

@dataclass
class Selector:
    """Unified selector for HTML and JSON."""

    # CSS selector (for HTML)
    element: str | None = None
    list: str | None = None

    # JSONPath selector (for JSON)
    jsonpath: str | None = None
    jsonpath_list: str | None = None

    # Common
    attribute: str | None = None
    value_template: Template | None = None
    extract: str = "text"
    on_error: OnError | None = None

    @property
    def is_list(self) -> bool:
        """Check if selector targets a list."""
        return self.list is not None or self.jsonpath_list is not None

    @property
    def is_json_selector(self) -> bool:
        """Check if this is a JSONPath selector."""
        return self.jsonpath is not None or self.jsonpath_list is not None

    @property
    def selector_string(self) -> str:
        """Get the actual selector string."""
        if self.is_json_selector:
            return self.jsonpath_list or self.jsonpath
        return self.list or self.element
```

**Example configuration** supporting both:

```yaml
multiscrape:
  - resource: https://api.example.com/data
    sensor:
      - name: "API Value"
        jsonpath: "$.data.temperature" # ← JSONPath for JSON APIs

  - resource: https://example.com/page
    sensor:
      - name: "HTML Value"
        select: "div.temperature" # ← CSS selector for HTML
```

### Benefits

1. **JSON Support**: Can now scrape JSON APIs natively
2. **Extensibility**: Easy to add YAML, XML parsers
3. **Clean Separation**: Parser selection logic isolated
4. **Better Errors**: "No parser available" vs "JSON cannot be scraped"
5. **Testability**: Can test each parser independently
6. **Performance**: Parser chosen once during `set_content()`

### Migration Path

1. Create parser hierarchy in `parsers.py`
2. Implement `JsonContent` with basic JSONPath
3. Update `Selector` to support JSONPath
4. Update schema to allow JSONPath selectors
5. Test with JSON APIs
6. Add documentation for JSONPath syntax
7. Optional: Integrate `jsonpath-ng` for advanced queries

---

## Implementation Timeline

### Phase 1: Foundation (Week 1-2)

- [ ] Priority Fix #1: Unify HTTP handling
- [ ] Priority Fix #2: Simplify variable system
- [ ] Create comprehensive tests for new components

### Phase 2: Parsing & Scraping (Week 3-4)

- [ ] Priority Fix #3: Refactor Scraper
- [ ] Priority Fix #6: Strategy pattern for parsers
- [ ] Add JSON support with JSONPath

### Phase 3: Architecture (Week 5-6)

- [ ] Priority Fix #4: Fix notification flow
- [ ] Priority Fix #5: Replace index-based discovery
- [ ] Update all existing tests

### Phase 4: Documentation & Migration (Week 7-8)

- [ ] Update configuration documentation
- [ ] Create migration guide
- [ ] Add architecture diagrams
- [ ] Release beta version for testing

---

## Testing Strategy

### Unit Tests

- `HttpSession` - auth flows, session management
- `ParserFactory` - parser selection
- `HtmlParser` / `JsonParser` - content parsing
- `ValueExtractor` - value extraction
- `VariableRenderer` - template rendering
- `ScraperRegistry` - registration and lookup

### Integration Tests

- Full scraping flow with HTML
- Full scraping flow with JSON
- Form authentication flow
- Error handling and retry
- Session invalidation and re-auth
- Platform loading and discovery

### Backwards Compatibility Tests

- Existing configurations still work
- State restoration works
- Services still function
- Reload works correctly

---

## Success Metrics

After refactoring, we should see:

1. **Reduced Complexity**

   - Scraper class: 197 lines → ~60 lines
   - Average method length: <20 lines
   - Cyclomatic complexity: <10 per method

2. **Improved Maintainability**

   - New parser added in <50 lines
   - New platform added without touching core
   - Bug fixes touch 1-2 files, not 5+

3. **Better Testing**

   - Unit test coverage: >90%
   - Integration test coverage: >80%
   - Each component tested independently

4. **Enhanced Features**
   - JSON API support
   - Automatic session management
   - Type-safe variable context
   - Better error messages

---

## Breaking Changes

### Configuration Changes

**None** - All existing configurations should continue to work.

### API Changes for Custom Components

If anyone extends this integration (unlikely but possible):

1. `Scraper.scrape()` signature changes to include `ScrapeContext`
2. `async_get_config_and_coordinator()` replaced with `get_scraper_for_platform()`
3. `hass.data[DOMAIN]` structure changes to use registry

**Migration**: Provide compatibility layer for one version, then deprecate.

---

## Questions & Decisions

### Q1: Should we use events or session validation for auth?

**Decision**: Start with session validation (simpler), migrate to events if needed.

### Q2: How much JSONPath support?

**Decision**: Basic support initially (dot notation, array indices), add `jsonpath-ng` if users need advanced queries.

### Q3: Breaking changes acceptable?

**Decision**: No breaking config changes. Internal API changes OK with deprecation warnings.

### Q4: Support config flow in this refactor?

**Decision**: No, keep as separate project. Focus on architecture cleanup first.

---

## References

- [Home Assistant DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data)
- [Strategy Pattern](https://refactoring.guru/design-patterns/strategy)
- [Law of Demeter](https://en.wikipedia.org/wiki/Law_of_Demeter)
- [JSONPath Specification](https://goessner.net/articles/JsonPath/)
