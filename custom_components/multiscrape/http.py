"""HTTP utility functions."""
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def merge_url_with_params(url, params):
    """Merge URL with parameters."""
    if not params:
        return url

    url_parts = list(urlparse(url))
    query = parse_qs(url_parts[4])
    query.update(params)
    url_parts[4] = urlencode(query, doseq=True)
    try:
        return urlunparse(url_parts)
    except Exception as ex:
        raise ValueError(f"Failed to merge URL with parameters: {ex}") from ex
