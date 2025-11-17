"""Tests for the coordinator module."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.multiscrape.coordinator import (
    ContentRequestManager, MultiscrapeDataUpdateCoordinator)


@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_content_request_manager_get_content_basic(
    content_request_manager, mock_http_wrapper
):
    """Test basic content retrieval without form submission."""
    # Arrange
    mock_http_wrapper.async_request.return_value.text = "<html>Test Content</html>"

    # Act
    result = await content_request_manager.get_content()

    # Assert
    assert result == "<html>Test Content</html>"
    mock_http_wrapper.async_request.assert_called_once()


@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_content_request_manager_with_form_submission(
    mock_http_wrapper, mock_resource_renderer, mock_http_response
):
    """Test content retrieval with form submission."""
    # Arrange
    mock_form = AsyncMock()
    mock_form.should_submit = True
    mock_form.async_submit = AsyncMock(
        return_value=("<html>Form Response</html>", {"cookie": "value"})
    )
    mock_form.scrape_variables = MagicMock(return_value={"var": "value"})

    manager = ContentRequestManager(
        config_name="test",
        http=mock_http_wrapper,
        resource_renderer=mock_resource_renderer,
        form=mock_form,
    )

    # Act
    result = await manager.get_content()

    # Assert
    assert result == "<html>Form Response</html>"
    mock_form.async_submit.assert_called_once()
    # HTTP request should NOT be called since form submission returned content
    mock_http_wrapper.async_request.assert_not_called()


@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_content_request_manager_form_submission_no_result(
    mock_http_wrapper, mock_resource_renderer, mock_http_response
):
    """Test content retrieval when form submission returns None."""
    # Arrange
    mock_form = AsyncMock()
    mock_form.should_submit = True
    mock_form.async_submit = AsyncMock(return_value=(None, {"cookie": "value"}))
    mock_form.scrape_variables = MagicMock(return_value={"var": "value"})

    manager = ContentRequestManager(
        config_name="test",
        http=mock_http_wrapper,
        resource_renderer=mock_resource_renderer,
        form=mock_form,
    )

    mock_http_wrapper.async_request.return_value = mock_http_response(
        text="<html>Page Content</html>"
    )

    # Act
    result = await manager.get_content()

    # Assert
    assert result == "<html>Page Content</html>"
    mock_http_wrapper.async_request.assert_called_once()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_coordinator_successful_update(coordinator, mock_http_wrapper, scraper):
    """Test successful data update through coordinator."""
    # Arrange
    mock_http_wrapper.async_request.return_value.text = "<html>Updated Content</html>"

    # Act
    await coordinator.async_refresh()

    # Assert
    assert coordinator.last_update_success
    assert not coordinator.update_error
    # Verify the scraper received the content
    assert scraper._data == "<html>Updated Content</html>"


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_coordinator_update_failure(coordinator, mock_http_wrapper):
    """Test coordinator behavior on update failure."""
    # Arrange
    mock_http_wrapper.async_request.side_effect = Exception("Network error")

    # Act
    await coordinator.async_refresh()

    # Assert
    assert coordinator.update_error
    # The coordinator should handle the exception gracefully


@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_coordinator_notify_scrape_exception(
    coordinator, content_request_manager, mock_form_submitter
):
    """Test that scrape exceptions are properly notified."""
    # Act
    coordinator.notify_scrape_exception()

    # Assert
    mock_form_submitter.notify_scrape_exception.assert_called_once()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_coordinator_with_zero_scan_interval(
    hass: HomeAssistant,
    content_request_manager,
    mock_file_manager,
    scraper,
    mock_http_wrapper,
):
    """Test coordinator with scan_interval set to zero (manual updates only).

    When scan_interval is 0, the coordinator should:
    1. Set _update_interval to None (disables automatic updates)
    2. Only update when manually triggered via async_request_refresh()
    """
    # Arrange
    coordinator = MultiscrapeDataUpdateCoordinator(
        config_name="test_coordinator",
        hass=hass,
        request_manager=content_request_manager,
        file_manager=mock_file_manager,
        scraper=scraper,
        update_interval=timedelta(seconds=0),
    )

    # Assert - interval is disabled
    assert coordinator._update_interval is None

    # Verify manual update still works
    mock_http_wrapper.async_request.return_value.text = "<html>Manual Update</html>"
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    assert scraper._data == "<html>Manual Update</html>"
    assert coordinator.last_update_success
