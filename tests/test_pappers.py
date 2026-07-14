from nodes import Address
import pappers_scrapper

def test_lookup():
    results = pappers_scrapper.lookup("Stanislas", "Jacob")
    print(results)
    assert isinstance(results, list)
    for result in results:
        assert hasattr(result, 'name')
        assert hasattr(result, 'address')
        assert hasattr(result, 'siret')
        assert hasattr(result, 'creation_date')
        assert hasattr(result, 'link')
        assert isinstance(result.address, Address)
        assert result.address.source == "Pappers"
        assert result.address.source_url == result.link