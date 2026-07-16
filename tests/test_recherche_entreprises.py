from unittest.mock import MagicMock, patch

import httpx
import pytest

import recherche_entreprises_scraper
from nodes import Address, Company


def _client(responses):
    """httpx.Client double whose `get()` returns each of `responses` in order, one per call."""
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.get.side_effect = responses
    return client


def _response(payload):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def _entry(nom_complet="ACME", siret="12345678900012", siren="123456789", nature_juridique="5499",
           dirigeants=None, numero_voie="1", type_voie="RUE", libelle_voie="DE LA PAIX",
           code_postal="75002", libelle_commune="PARIS", date_creation="2000-01-01"):
    return {
        "siren": siren,
        "nom_complet": nom_complet,
        "date_creation": date_creation,
        "nature_juridique": nature_juridique,
        "siege": {
            "siret": siret,
            "numero_voie": numero_voie,
            "type_voie": type_voie,
            "libelle_voie": libelle_voie,
            "code_postal": code_postal,
            "libelle_commune": libelle_commune,
        },
        "dirigeants": dirigeants or [],
    }


def test_lookup_returns_empty_list_on_zero_results():
    response = _response({"results": [], "total_pages": 1})
    mock_client = _client([response])

    with patch("recherche_entreprises_scraper.httpx.Client", return_value=mock_client):
        results = recherche_entreprises_scraper.lookup("John", "Doe")

    assert results == []
    params = mock_client.get.call_args.kwargs["params"]
    assert params["prenoms_personne"] == "John"
    assert params["nom_personne"] == "Doe"
    assert params["type_personne"] == "dirigeant"


def test_lookup_raises_recherche_entreprises_error_on_http_failure():
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError("boom", request=MagicMock(), response=MagicMock())
    mock_client = _client([response])

    with patch("recherche_entreprises_scraper.httpx.Client", return_value=mock_client):
        with pytest.raises(recherche_entreprises_scraper.RechercheEntreprisesError):
            recherche_entreprises_scraper.lookup("John", "Doe")


def test_lookup_returns_company_with_director_and_skips_personne_morale():
    entry = _entry(dirigeants=[
        {"nom": "Bounias", "prenoms": "Bernard", "date_de_naissance": "1966-02",
         "qualite": "Gérant", "type_dirigeant": "personne physique"},
        {"siren": "999999999", "denomination": "HOLDCO",
         "qualite": "Commissaire aux comptes", "type_dirigeant": "personne morale"},
    ])
    response = _response({"results": [entry], "total_pages": 1})

    with patch("recherche_entreprises_scraper.httpx.Client", return_value=_client([response])):
        results = recherche_entreprises_scraper.lookup("Bernard", "Bounias")

    assert len(results) == 1
    company = results[0]
    assert isinstance(company, Company)
    assert company.name == "ACME"
    assert company.siret == "12345678900012"
    assert isinstance(company.address, Address)
    assert company.address.street == "1 RUE DE LA PAIX"
    assert company.address.city == "PARIS"
    assert company.address.postal_code == "75002"
    assert company.address.source == "Recherche d'entreprises"
    assert company.address.source_url == "https://annuaire-entreprises.data.gouv.fr/entreprise/123456789"
    assert company.legal_form == "Société à responsabilité limitée (SARL)"

    assert len(company.directors) == 1
    director = company.directors[0]
    assert director.role == "Gérant"
    assert director.since_date == ""
    assert director.person.first_name == "Bernard"
    assert director.person.last_name == "Bounias"
    assert director.person.birth_date == "1966-02"


def test_lookup_falls_back_to_raw_code_for_unknown_legal_form():
    response = _response({"results": [_entry(nature_juridique="9999")], "total_pages": 1})

    with patch("recherche_entreprises_scraper.httpx.Client", return_value=_client([response])):
        results = recherche_entreprises_scraper.lookup("Jean", "Dupont")

    assert results[0].legal_form == "9999"


def test_lookup_paginates_through_multiple_result_pages():
    entry1 = _entry(nom_complet="Alpha", siret="11111111100011", siren="111111111")
    entry2 = _entry(nom_complet="Beta", siret="22222222200022", siren="222222222")
    response1 = _response({"results": [entry1], "total_pages": 2})
    response2 = _response({"results": [entry2], "total_pages": 2})
    mock_client = _client([response1, response2])

    with patch("recherche_entreprises_scraper.httpx.Client", return_value=mock_client):
        results = recherche_entreprises_scraper.lookup("Ada", "Lovelace")

    assert {c.name for c in results} == {"Alpha", "Beta"}
    assert mock_client.get.call_count == 2
    assert mock_client.get.call_args_list[0].kwargs["params"]["page"] == 1
    assert mock_client.get.call_args_list[1].kwargs["params"]["page"] == 2
