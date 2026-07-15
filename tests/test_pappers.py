from nodes import Address
import pappers_scrapper
"""
def test_lookup():
    results = pappers_scrapper.lookup("John", "Doe")
    print(results)
    assert isinstance(results, list)
    for result in results:
        assert hasattr(result, 'name')
        assert hasattr(result, 'address')
        assert hasattr(result, 'siret')
        assert hasattr(result, 'creation_date')
        assert hasattr(result, 'link')
        assert hasattr(result, 'legal_form')
        assert isinstance(result.address, Address)
        assert result.address.source == "Pappers"
        assert result.address.source_url == result.link
"""