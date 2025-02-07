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
