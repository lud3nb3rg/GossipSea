import holehe_scraper
from nodes import OnlineAccount


def test_lookup():
    results = holehe_scraper.lookup("test@gmail.com")
    print(results)
    assert isinstance(results, list)
    for result in results:
        assert isinstance(result, OnlineAccount)
        assert hasattr(result, "site")
        assert hasattr(result, "domain")
        assert result.source == "holehe"
