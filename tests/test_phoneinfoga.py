from unittest.mock import MagicMock, patch

import httpx
import pytest

import phoneinfoga_scraper
from nodes import PhoneNumber


def _mock_client(post_response, get_response):
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.return_value = post_response
    client.get.return_value = get_response
    return client


def test_lookup_returns_single_item_list_with_local_scan_data():
    post_response = MagicMock()
    get_response = MagicMock()
    get_response.json.return_value = {"local": {"country": "France", "carrier": "Orange"}}

    with patch("phoneinfoga_scraper.httpx.Client", return_value=_mock_client(post_response, get_response)):
        results = phoneinfoga_scraper.lookup("+33612345678")

    assert isinstance(results, list)
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, PhoneNumber)
    assert result.number == "+33612345678"
    assert result.country == "France"
    assert result.carrier == "Orange"
    assert result.source == "Phoneinfoga"


def test_lookup_raises_phoneinfoga_error_on_http_failure():
    post_response = MagicMock()
    post_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=MagicMock(), response=MagicMock()
    )
    get_response = MagicMock()

    with patch("phoneinfoga_scraper.httpx.Client", return_value=_mock_client(post_response, get_response)):
        with pytest.raises(phoneinfoga_scraper.PhoneinfogaError):
            phoneinfoga_scraper.lookup("+33612345678")
