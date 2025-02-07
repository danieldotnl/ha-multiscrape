"""Tests for the http module."""
from custom_components.multiscrape.http import merge_url_with_params


def test_merge_url_with_params():
    """Test merge_url_with_params function."""
    url = "https://example.com"
    params = {"param1": "value1", "param2": "value2"}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value1&param2=value2"

    url = "https://example.com"
    params = {"param1": "value1", "param2": 2}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value1&param2=2"

    url = "https://example.com?param1=value1"
    params = {"param2": "value2"}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value1&param2=value2"

    url = "https://example.com?param1=value1"
    params = {}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value1"

    url = "https://example.com?param1=33"
    params = None
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=33"


def test_merge_url_with_params_existing_params():
    """Test merge_url_with_params with existing URL parameters."""
    url = "https://example.com?param1=value1"
    params = {"param2": "value2"}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value1&param2=value2"

    url = "https://example.com?param1=value1&param2=value2"
    params = {"param3": "value3"}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value1&param2=value2&param3=value3"


def test_merge_url_with_params_override_existing():
    """Test merge_url_with_params overriding existing URL parameters."""
    url = "https://example.com?param1=value1"
    params = {"param1": "new_value1", "param2": "value2"}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=new_value1&param2=value2"


def test_merge_url_with_params_array_values():
    """Test merge_url_with_params with array values."""
    url = "https://example.com"
    params = {"param1": ["value1", "value2"]}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value1&param1=value2"

    url = "https://example.com?param1=value1"
    params = {"param1": ["value2", "value3"]}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value2&param1=value3"


def test_merge_url_with_params_special_characters():
    """Test merge_url_with_params with special characters in parameters."""
    url = "https://example.com"
    params = {"param1": "value with spaces",
              "param2": "value&with&special&chars"}
    result = merge_url_with_params(url, params)
    assert result == "https://example.com?param1=value+with+spaces&param2=value%26with%26special%26chars"
