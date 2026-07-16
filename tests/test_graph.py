import json

import graph_html
from graph import GossipGraph
from nodes import Address, Director, OnlineAccount, Person, PhoneNumber
from recherche_entreprises_scraper import Company


def _sample_results() -> list[Company]:
    address = Address("1 Rue de la Paix", "Paris", "75002", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    person = Person("Jean", "Dupont", birth_date="1980-05", birth_place="Paris",
                     source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    director = Director(person, "Président", "01/01/2020")
    company = Company(
        name="ACME SARL",
        address=address,
        siret="12345678900012",
        creation_date="01/01/2020",
        link="https://annuaire-entreprises.data.gouv.fr/entreprise/1",
        directors=[director],
        legal_form="SARL",
    )
    return [company]


def test_to_graph_data_is_json_serializable_and_consistent():
    graph = GossipGraph()
    graph.load_recherche_entreprises(_sample_results())

    data = graph.to_graph_data()
    json.dumps(data)  # must not raise

    assert len(data["nodes"]) == 3  # person, address, company
    assert len(data["edges"]) == 2  # HAS_ADDRESS, DIRECTOR_OF

    node_ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["from"] in node_ids
        assert edge["to"] in node_ids

    person_node = next(n for n in data["nodes"] if n["type"] == "Person")
    assert person_node["source"] == "Recherche d'entreprises"
    assert person_node["source_url"] == "https://annuaire-entreprises.data.gouv.fr/entreprise/1"
    assert person_node["key"] == {"first_name_key": "jean", "last_name_key": "dupont", "birth_date_key": "1980-05"}
    assert person_node["merge_props"] == {
        "first_name": "Jean", "last_name": "Dupont", "birth_date": "1980-05", "birth_place": "Paris",
    }

    address_node = next(n for n in data["nodes"] if n["type"] == "Address")
    assert address_node["source"] == "Recherche d'entreprises"
    assert address_node["key"] == {
        "street_key": "1 rue de la paix", "city_key": "paris", "postal_code_key": "75002",
    }
    assert address_node["merge_props"] == {
        "street": "1 Rue de la Paix", "city": "Paris", "postal_code": "75002",
    }

    company_node = next(n for n in data["nodes"] if n["type"] == "Company")
    assert company_node["key"] == {"siret_key": "12345678900012"}
    assert company_node["properties"]["Legal form"] == "SARL"
    assert company_node["merge_props"]["legal_form"] == "SARL"

    # An ordinary SARL is not a probable home address for its director.
    assert not any(e["type"] == "PROBABLE_HOME" for e in data["edges"])


def test_addresses_merge_case_insensitively_on_street_city_and_postal_code():
    address_a = Address("1 Rue de la Paix", "Paris", "75002", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    address_b = Address("1 RUE DE LA PAIX", "PARIS", "75002", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/2")
    company_a = Company(
        name="ACME SARL", address=address_a, siret="12345678900012",
        creation_date="01/01/2020", link="https://annuaire-entreprises.data.gouv.fr/entreprise/1", directors=[],
    )
    company_b = Company(
        name="OTHER SARL", address=address_b, siret="98765432100099",
        creation_date="01/01/2021", link="https://annuaire-entreprises.data.gouv.fr/entreprise/2", directors=[],
    )

    graph = GossipGraph()
    graph.load_recherche_entreprises([company_a, company_b])
    data = graph.to_graph_data()

    address_nodes = [n for n in data["nodes"] if n["type"] == "Address"]
    assert len(address_nodes) == 1
    # First-seen casing is preserved for display.
    assert address_nodes[0]["merge_props"]["street"] == "1 Rue de la Paix"


def test_persons_and_companies_merge_case_insensitively():
    address = Address("1 Rue de la Paix", "Paris", "75002", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    person_a = Person("Jean", "Dupont", birth_date="1980-05", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    person_b = Person("JEAN", "DUPONT", birth_date="1980-05", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/2")
    company_a = Company(
        name="ACME SARL", address=address, siret="12345678900012", creation_date="01/01/2020",
        link="https://annuaire-entreprises.data.gouv.fr/entreprise/1", directors=[Director(person_a, "Président", "01/01/2020")],
    )
    company_b = Company(
        name="acme sarl", address=address, siret="12345678900012", creation_date="01/01/2020",
        link="https://annuaire-entreprises.data.gouv.fr/entreprise/2", directors=[Director(person_b, "Gérant", "01/01/2021")],
    )

    graph = GossipGraph()
    graph.load_recherche_entreprises([company_a, company_b])
    data = graph.to_graph_data()

    person_nodes = [n for n in data["nodes"] if n["type"] == "Person"]
    company_nodes = [n for n in data["nodes"] if n["type"] == "Company"]
    assert len(person_nodes) == 1
    assert len(company_nodes) == 1
    # Same (person, company) relationship seen twice under different casing dedupes to one edge.
    director_edges = [e for e in data["edges"] if e["type"] == "DIRECTOR_OF"]
    assert len(director_edges) == 1


def test_probable_home_edge_created_for_entrepreneur_individuel():
    address = Address("1 Rue de la Paix", "Paris", "75002", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    person = Person("Jean", "Dupont", birth_date="1980-05", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    director = Director(person, "Exploitant", "01/01/2020")
    company = Company(
        name="Jean Dupont EI", address=address, siret="12345678900012", creation_date="01/01/2020",
        link="https://annuaire-entreprises.data.gouv.fr/entreprise/1", directors=[director],
        legal_form="entrepreneur individuel",  # different casing than the match set, on purpose
    )

    graph = GossipGraph()
    graph.load_recherche_entreprises([company])
    data = graph.to_graph_data()

    home_edges = [e for e in data["edges"] if e["type"] == "PROBABLE_HOME"]
    assert len(home_edges) == 1
    addr_id = next(n["id"] for n in data["nodes"] if n["type"] == "Address")
    person_id = next(n["id"] for n in data["nodes"] if n["type"] == "Person")
    assert home_edges[0]["from"] == addr_id
    assert home_edges[0]["to"] == person_id


def test_probable_home_edge_created_for_sci():
    address = Address("1 Rue de la Paix", "Paris", "75002", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    person_a = Person("Jean", "Dupont", birth_date="1980-05", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    person_b = Person("Marie", "Martin", birth_date="1982-03", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    company = Company(
        name="SCI Les Tilleuls", address=address, siret="12345678900012", creation_date="01/01/2020",
        link="https://annuaire-entreprises.data.gouv.fr/entreprise/1",
        directors=[Director(person_a, "Gérant", "01/01/2020"), Director(person_b, "Gérante", "01/01/2020")],
        legal_form="SCI, Société Civile Immobilière",
    )

    graph = GossipGraph()
    graph.load_recherche_entreprises([company])
    data = graph.to_graph_data()

    home_edges = [e for e in data["edges"] if e["type"] == "PROBABLE_HOME"]
    assert len(home_edges) == 2


def test_add_original_person_merges_matching_director_and_enriches_birth_date():
    graph = GossipGraph()
    graph.add_original_person("Jean", "Dupont")
    graph.load_recherche_entreprises(_sample_results())

    data = graph.to_graph_data()
    person_nodes = [n for n in data["nodes"] if n["type"] == "Person"]
    assert len(person_nodes) == 1
    assert person_nodes[0]["key"] == {"first_name_key": "jean", "last_name_key": "dupont", "birth_date_key": None}
    assert person_nodes[0]["properties"]["Birth date"] == "1980-05"

    director_edges = [e for e in data["edges"] if e["type"] == "DIRECTOR_OF"]
    assert len(director_edges) == 1
    assert director_edges[0]["from"] == person_nodes[0]["id"]


def test_add_original_person_merges_director_with_extra_given_names():
    address = Address("1 Rue de la Paix", "Paris", "75002", source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    person = Person("Stanislas Karol", "Jacob", birth_date="1980-05",
                     source="Recherche d'entreprises", source_url="https://annuaire-entreprises.data.gouv.fr/entreprise/1")
    director = Director(person, "Président", "01/01/2020")
    company = Company(
        name="ACME SARL", address=address, siret="12345678900012", creation_date="01/01/2020",
        link="https://annuaire-entreprises.data.gouv.fr/entreprise/1", directors=[director], legal_form="SARL",
    )

    graph = GossipGraph()
    graph.add_original_person("Stanislas", "Jacob")
    graph.load_recherche_entreprises([company])

    data = graph.to_graph_data()
    person_nodes = [n for n in data["nodes"] if n["type"] == "Person"]
    assert len(person_nodes) == 1
    assert person_nodes[0]["key"] == {"first_name_key": "stanislas", "last_name_key": "jacob", "birth_date_key": None}
    assert person_nodes[0]["properties"]["Birth date"] == "1980-05"

    director_edges = [e for e in data["edges"] if e["type"] == "DIRECTOR_OF"]
    assert len(director_edges) == 1
    assert director_edges[0]["from"] == person_nodes[0]["id"]


def test_original_person_and_email_have_provided_by_user_source_and_are_linked():
    graph = GossipGraph()
    graph.add_original_person("Jean", "Dupont")
    graph.add_original_email("jean.dupont@example.com")

    data = graph.to_graph_data()
    person_node = next(n for n in data["nodes"] if n["type"] == "Person")
    email_node = next(n for n in data["nodes"] if n["type"] == "Email")
    assert person_node["source"] == "Provided by user"
    assert email_node["source"] == "Provided by user"

    email_edges = [e for e in data["edges"] if e["type"] == "EMAIL"]
    assert len(email_edges) == 1
    assert email_edges[0]["from"] == person_node["id"]
    assert email_edges[0]["to"] == email_node["id"]


def test_original_person_and_email_link_regardless_of_call_order():
    graph = GossipGraph()
    graph.add_original_email("jean.dupont@example.com")
    graph.add_original_person("Jean", "Dupont")

    data = graph.to_graph_data()
    email_edges = [e for e in data["edges"] if e["type"] == "EMAIL"]
    assert len(email_edges) == 1


def test_load_recherche_entreprises_before_add_original_person_does_not_retroactively_merge():
    graph = GossipGraph()
    graph.load_recherche_entreprises(_sample_results())
    graph.add_original_person("Jean", "Dupont")

    data = graph.to_graph_data()
    assert len([n for n in data["nodes"] if n["type"] == "Person"]) == 2


def test_load_holehe_creates_email_and_account_nodes_with_edge():
    graph = GossipGraph()
    graph.add_original_email("someone@example.com")
    account = OnlineAccount(site="twitter", domain="twitter.com", method="register", source="holehe")
    graph.load_holehe("someone@example.com", [account])

    data = graph.to_graph_data()
    email_nodes = [n for n in data["nodes"] if n["type"] == "Email"]
    account_nodes = [n for n in data["nodes"] if n["type"] == "OnlineAccount"]
    reg_edges = [e for e in data["edges"] if e["type"] == "REGISTERED_ON"]

    assert len(email_nodes) == 1
    assert len(account_nodes) == 1
    assert len(reg_edges) == 1
    assert reg_edges[0]["from"] == email_nodes[0]["id"]
    assert reg_edges[0]["to"] == account_nodes[0]["id"]
    assert account_nodes[0]["properties"]["Method"] == "register"


def test_load_holehe_creates_email_node_even_without_add_original_email():
    graph = GossipGraph()
    account = OnlineAccount(site="twitter", domain="twitter.com", source="holehe")
    graph.load_holehe("noone@example.com", [account])

    data = graph.to_graph_data()
    assert any(n["type"] == "Email" for n in data["nodes"])


def test_original_person_and_phone_have_provided_by_user_source_and_are_linked():
    graph = GossipGraph()
    graph.add_original_person("Jean", "Dupont")
    graph.add_original_phone("+33612345678")

    data = graph.to_graph_data()
    person_node = next(n for n in data["nodes"] if n["type"] == "Person")
    phone_node = next(n for n in data["nodes"] if n["type"] == "PhoneNumber")
    assert person_node["source"] == "Provided by user"
    assert phone_node["source"] == "Provided by user"

    phone_edges = [e for e in data["edges"] if e["type"] == "PHONE"]
    assert len(phone_edges) == 1
    assert phone_edges[0]["from"] == person_node["id"]
    assert phone_edges[0]["to"] == phone_node["id"]


def test_original_person_and_phone_link_regardless_of_call_order():
    graph = GossipGraph()
    graph.add_original_phone("+33612345678")
    graph.add_original_person("Jean", "Dupont")

    data = graph.to_graph_data()
    phone_edges = [e for e in data["edges"] if e["type"] == "PHONE"]
    assert len(phone_edges) == 1


def test_load_phoneinfoga_enriches_original_phone_node_in_place():
    graph = GossipGraph()
    graph.add_original_phone("+33612345678")
    result = PhoneNumber("+33612345678", country="France", carrier="Orange", source="Phoneinfoga")
    graph.load_phoneinfoga("+33612345678", [result])

    data = graph.to_graph_data()
    phone_nodes = [n for n in data["nodes"] if n["type"] == "PhoneNumber"]
    assert len(phone_nodes) == 1
    assert phone_nodes[0]["properties"]["Country"] == "France"
    assert phone_nodes[0]["properties"]["Carrier"] == "Orange"
    # Enrichment doesn't override the "Provided by user" identity source.
    assert phone_nodes[0]["source"] == "Provided by user"


def test_original_person_and_username_have_provided_by_user_source_and_are_linked():
    graph = GossipGraph()
    graph.add_original_person("Jean", "Dupont")
    graph.add_original_username("jdupont")

    data = graph.to_graph_data()
    person_node = next(n for n in data["nodes"] if n["type"] == "Person")
    username_node = next(n for n in data["nodes"] if n["type"] == "Username")
    assert person_node["source"] == "Provided by user"
    assert username_node["source"] == "Provided by user"

    username_edges = [e for e in data["edges"] if e["type"] == "USERNAME"]
    assert len(username_edges) == 1
    assert username_edges[0]["from"] == person_node["id"]
    assert username_edges[0]["to"] == username_node["id"]


def test_original_person_and_username_link_regardless_of_call_order():
    graph = GossipGraph()
    graph.add_original_username("jdupont")
    graph.add_original_person("Jean", "Dupont")

    data = graph.to_graph_data()
    username_edges = [e for e in data["edges"] if e["type"] == "USERNAME"]
    assert len(username_edges) == 1


def test_add_extrapolated_username_creates_extrapolated_edge_not_username_edge():
    graph = GossipGraph()
    graph.add_original_person("Jean", "Dupont")
    graph.add_extrapolated_username("jeandupont1990")

    data = graph.to_graph_data()
    person_node = next(n for n in data["nodes"] if n["type"] == "Person")
    username_node = next(n for n in data["nodes"] if n["type"] == "Username")
    assert username_node["source"] == "Extrapolated"

    assert not any(e["type"] == "USERNAME" for e in data["edges"])
    extrapolated_edges = [e for e in data["edges"] if e["type"] == "EXTRAPOLATED_USERNAME"]
    assert len(extrapolated_edges) == 1
    assert extrapolated_edges[0]["from"] == person_node["id"]
    assert extrapolated_edges[0]["to"] == username_node["id"]


def test_add_extrapolated_username_without_original_person_is_a_noop():
    graph = GossipGraph()
    graph.add_extrapolated_username("jeandupont1990")

    data = graph.to_graph_data()
    assert data["nodes"] == []
    assert data["edges"] == []


def test_add_extrapolated_email_links_from_username_not_person():
    graph = GossipGraph()
    graph.add_extrapolated_email("jdupont", "jdupont@gmail.com")

    data = graph.to_graph_data()
    username_node = next(n for n in data["nodes"] if n["type"] == "Username")
    email_node = next(n for n in data["nodes"] if n["type"] == "Email")
    assert username_node["source"] == "Extrapolated"
    assert email_node["source"] == "Extrapolated"

    assert not any(e["type"] == "EMAIL" for e in data["edges"])
    extrapolated_edges = [e for e in data["edges"] if e["type"] == "EXTRAPOLATED_EMAIL"]
    assert len(extrapolated_edges) == 1
    assert extrapolated_edges[0]["from"] == username_node["id"]
    assert extrapolated_edges[0]["to"] == email_node["id"]


def test_load_sherlock_creates_username_and_account_nodes_with_edge():
    graph = GossipGraph()
    graph.add_original_username("jdupont")
    account = OnlineAccount(site="GitHub", domain="github.com", method="username_search", source="Sherlock")
    graph.load_sherlock("jdupont", [account])

    data = graph.to_graph_data()
    username_nodes = [n for n in data["nodes"] if n["type"] == "Username"]
    account_nodes = [n for n in data["nodes"] if n["type"] == "OnlineAccount"]
    reg_edges = [e for e in data["edges"] if e["type"] == "REGISTERED_ON"]

    assert len(username_nodes) == 1
    assert len(account_nodes) == 1
    assert len(reg_edges) == 1
    assert reg_edges[0]["from"] == username_nodes[0]["id"]
    assert reg_edges[0]["to"] == account_nodes[0]["id"]


def test_load_maigret_creates_username_node_even_without_add_original_username():
    graph = GossipGraph()
    account = OnlineAccount(site="GitHub", domain="github.com", source="Maigret")
    graph.load_maigret("jdupont", [account])

    data = graph.to_graph_data()
    assert any(n["type"] == "Username" for n in data["nodes"])


def test_render_html_embeds_valid_graph_data():
    graph = GossipGraph()
    graph.load_recherche_entreprises(_sample_results())
    data = graph.to_graph_data()

    html = graph_html.render_html(data)

    assert "vis-network" in html
    start = html.index("const GRAPH_DATA = ") + len("const GRAPH_DATA = ")
    end = html.index(";\n", start)
    embedded = json.loads(html[start:end])
    assert embedded == data
