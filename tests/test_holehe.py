from unittest.mock import patch

import holehe_scraper
from nodes import OnlineAccount

# Maps a fake "module" identity (what get_functions would normally return one per
# holehe checker module) to the canned result dict launch_module would append to its
# `out` list for that module.
_CANNED_RESULTS = {
    "twitter": {"name": "twitter", "domain": "twitter.com", "method": "login", "exists": True},
    "github": {"name": "github", "domain": "github.com", "method": "login", "exists": False},
}


async def _fake_launch_module(module, email, client, out):
    out.append(_CANNED_RESULTS[module])


def test_lookup_returns_only_accounts_that_exist():
    with patch("holehe_scraper.import_submodules", return_value={}), \
         patch("holehe_scraper.get_functions", return_value=list(_CANNED_RESULTS.keys())), \
         patch("holehe_scraper.launch_module", side_effect=_fake_launch_module):
        results = holehe_scraper.lookup("test@gmail.com")

    assert isinstance(results, list)
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, OnlineAccount)
    assert result.site == "twitter"
    assert result.domain == "twitter.com"
    assert result.source == "holehe"


def test_lookup_returns_empty_list_when_nothing_exists():
    async def fake_launch_module(module, email, client, out):
        out.append({"name": module, "domain": f"{module}.com", "method": "login", "exists": False})

    with patch("holehe_scraper.import_submodules", return_value={}), \
         patch("holehe_scraper.get_functions", return_value=["github"]), \
         patch("holehe_scraper.launch_module", side_effect=fake_launch_module):
        results = holehe_scraper.lookup("test@gmail.com")

    assert results == []
