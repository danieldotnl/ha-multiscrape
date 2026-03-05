"""Tests for the coordinator module."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.multiscrape.const import MAX_RETRIES
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


# ============================================================================
# Retry logic tests (scan_interval=0)
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_coordinator_zero_interval_retries_on_failure(
    hass: HomeAssistant,
    content_request_manager,
    mock_file_manager,
    scraper,
    mock_http_wrapper,
):
    """Test that zero-interval coordinator schedules a retry on failure.

    When scan_interval=0, there's no automatic refresh interval. On failure,
    the coordinator should schedule a one-shot retry instead of silently failing.
    """
    coordinator = MultiscrapeDataUpdateCoordinator(
        config_name="test_retry",
        hass=hass,
        request_manager=content_request_manager,
        file_manager=mock_file_manager,
        scraper=scraper,
        update_interval=timedelta(seconds=0),
    )
    assert coordinator._update_interval is None
    assert coordinator._retry_count == 0

    # Simulate failed content retrieval
    mock_http_wrapper.async_request.side_effect = Exception("Network error")

    with patch(
        "custom_components.multiscrape.coordinator.event.async_track_point_in_utc_time"
    ) as mock_track:
        # Patch internals that are set up during full coordinator lifecycle
        coordinator._async_unsub_refresh = MagicMock()
        coordinator._job = MagicMock()
        coordinator._microsecond = 0
        await coordinator._async_update_data()

    # Assert
    assert coordinator._retry_count == 1
    assert coordinator.update_error is True
    mock_track.assert_called_once()


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_coordinator_zero_interval_stops_after_max_retries(
    hass: HomeAssistant,
    content_request_manager,
    mock_file_manager,
    scraper,
    mock_http_wrapper,
    caplog,
):
    """Test that zero-interval coordinator stops retrying after MAX_RETRIES."""
    coordinator = MultiscrapeDataUpdateCoordinator(
        config_name="test_max_retry",
        hass=hass,
        request_manager=content_request_manager,
        file_manager=mock_file_manager,
        scraper=scraper,
        update_interval=timedelta(seconds=0),
    )
    coordinator._retry_count = MAX_RETRIES

    mock_http_wrapper.async_request.side_effect = Exception("Network error")

    with patch(
        "custom_components.multiscrape.coordinator.event.async_track_point_in_utc_time"
    ) as mock_track:
        coordinator._async_unsub_refresh = MagicMock()
        await coordinator._async_update_data()

    # Assert - no more retries scheduled
    assert coordinator._retry_count == MAX_RETRIES + 1
    mock_track.assert_not_called()
    assert "please manually retry with trigger service" in caplog.text


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_coordinator_zero_interval_resets_retry_on_success(
    hass: HomeAssistant,
    content_request_manager,
    mock_file_manager,
    scraper,
    mock_http_wrapper,
):
    """Test that a successful update resets the retry counter."""
    coordinator = MultiscrapeDataUpdateCoordinator(
        config_name="test_reset_retry",
        hass=hass,
        request_manager=content_request_manager,
        file_manager=mock_file_manager,
        scraper=scraper,
        update_interval=timedelta(seconds=0),
    )
    coordinator._retry_count = 2

    mock_http_wrapper.async_request.return_value.text = "<html>Success</html>"

    await coordinator._async_update_data()

    # Assert - retry count reset
    assert coordinator._retry_count == 0
    assert coordinator.update_error is False


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_coordinator_nonzero_interval_does_not_retry(
    coordinator, mock_http_wrapper
):
    """Test that non-zero interval coordinator does not use retry mechanism.

    Retry scheduling is only for scan_interval=0 configs. Normal interval-based
    coordinators rely on the next scheduled refresh instead.
    """
    assert coordinator._retry_count == 0

    mock_http_wrapper.async_request.side_effect = Exception("Network error")

    await coordinator._async_update_data()

    # Assert - retry count NOT incremented (retry logic is only for interval=None)
    assert coordinator._retry_count == 0
    assert coordinator.update_error is True


# ============================================================================
# _prepare_new_run tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_coordinator_prepare_new_run_clears_state(
    coordinator, mock_file_manager
):
    """Test that _prepare_new_run resets state for a fresh update cycle."""
    # Set up dirty state
    coordinator.update_error = True

    await coordinator._prepare_new_run()

    # Assert
    assert coordinator.update_error is False
    mock_file_manager.empty_folder.assert_called_once()


# ============================================================================
# Form variables property chain
# ============================================================================


@pytest.mark.unit
@pytest.mark.async_test
@pytest.mark.timeout(5)
async def test_coordinator_form_variables_delegates_to_request_manager(
    coordinator, content_request_manager
):
    """Test that coordinator.form_variables returns request_manager.form_variables."""
    content_request_manager._form_variables = {"x-token": "abc123"}
    assert coordinator.form_variables == {"x-token": "abc123"}
