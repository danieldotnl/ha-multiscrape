"""Tests for the http module."""
import pytest

from custom_components.multiscrape.http import merge_url_with_params


@pytest.mark.unit
@pytest.mark.timeout(2)
@pytest.mark.parametrize(
    "url,params,expected",
    [
        # Basic parameter merging
        (
            "https://example.com",
            {"param1": "value1", "param2": "value2"},
            "https://example.com?param1=value1&param2=value2",
        ),
        # Integer parameter value
        (
            "https://example.com",
            {"param1": "value1", "param2": 2},
            "https://example.com?param1=value1&param2=2",
        ),
        # Merging with existing params
        (
            "https://example.com?param1=value1",
            {"param2": "value2"},
            "https://example.com?param1=value1&param2=value2",
        ),
        # Empty params dict
        (
            "https://example.com?param1=value1",
            {},
            "https://example.com?param1=value1",
        ),
        # None params
        (
            "https://example.com?param1=33",
            None,
            "https://example.com?param1=33",
        ),
        # Multiple existing params
        (
            "https://example.com?param1=value1&param2=value2",
            {"param3": "value3"},
            "https://example.com?param1=value1&param2=value2&param3=value3",
        ),
    ],
)
def test_merge_url_with_params(url, params, expected):
    """Test merge_url_with_params function with various inputs."""
    result = merge_url_with_params(url, params)
    assert result == expected


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_merge_url_with_params_override_existing():
    """Test merge_url_with_params overriding existing URL parameters."""
    url = "https://example.com?param1=value1"
    params = {"param1": "new_value1", "param2": "value2"}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=new_value1&param2=value2"


@pytest.mark.unit
@pytest.mark.timeout(2)
@pytest.mark.parametrize(
    "url,params,expected",
    [
        # Single array parameter
        (
            "https://example.com",
            {"param1": ["value1", "value2"]},
            "https://example.com?param1=value1&param1=value2",
        ),
        # Array parameter overriding existing
        (
            "https://example.com?param1=value1",
            {"param1": ["value2", "value3"]},
            "https://example.com?param1=value2&param1=value3",
        ),
    ],
)
def test_merge_url_with_params_array_values(url, params, expected):
    """Test merge_url_with_params with array values."""
    result = merge_url_with_params(url, params)
    assert result == expected


@pytest.mark.unit
@pytest.mark.timeout(2)
def test_merge_url_with_params_special_characters():
    """Test merge_url_with_params with special characters in parameters."""
    url = "https://example.com"
    params = {"param1": "value with spaces", "param2": "value&with&special&chars"}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value+with+spaces&param2=value%26with%26special%26chars"


@pytest.mark.unit
@pytest.mark.timeout(2)
@pytest.mark.parametrize(
    "url,params,expected",
    [
        # URL with port
        (
            "https://example.com:8080",
            {"param1": "value1"},
            "https://example.com:8080?param1=value1",
        ),
        # URL with fragment
        (
            "https://example.com#section1",
            {"param1": "value1"},
            "https://example.com?param1=value1#section1",
        ),
    ],
)
def test_merge_url_with_params_url_components(url, params, expected):
    """Test merge_url_with_params with various URL components."""
    result = merge_url_with_params(url, params)
    assert result == expected
