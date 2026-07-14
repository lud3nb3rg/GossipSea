import json

import graph_html
from graph import GossipGraph
from nodes import Address, Director, Person
from pappers_scrapper import PapperResultSociety


def _sample_results() -> list[PapperResultSociety]:
    address = Address("1 Rue de la Paix", "Paris", "75002", source="Pappers", source_url="https://www.pappers.fr/entreprise/1")
    person = Person("Jean", "Dupont", birth_date="1980-05", birth_place="Paris",
                     source="Pappers", source_url="https://www.pappers.fr/entreprise/1")
    director = Director(person, "Président", "01/01/2020")
    company = PapperResultSociety(
        name="ACME SARL",
        address=address,
        siret="12345678900012",
        creation_date="01/01/2020",
        link="https://www.pappers.fr/entreprise/1",
        directors=[director],
    )
    return [company]


def test_to_graph_data_is_json_serializable_and_consistent():
    graph = GossipGraph()
    graph.load_pappers(_sample_results())

    data = graph.to_graph_data()
    json.dumps(data)  # must not raise

    assert len(data["nodes"]) == 3  # person, address, company
    assert len(data["edges"]) == 2  # HAS_ADDRESS, DIRECTOR_OF

    node_ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["from"] in node_ids
        assert edge["to"] in node_ids

    person_node = next(n for n in data["nodes"] if n["type"] == "Person")
    assert person_node["source"] == "Pappers"
    assert person_node["source_url"] == "https://www.pappers.fr/entreprise/1"
    assert person_node["key"] == {"first_name_key": "jean", "last_name_key": "dupont", "birth_date_key": "1980-05"}
    assert person_node["merge_props"] == {
        "first_name": "Jean", "last_name": "Dupont", "birth_date": "1980-05", "birth_place": "Paris",
    }

    address_node = next(n for n in data["nodes"] if n["type"] == "Address")
    assert address_node["source"] == "Pappers"
    assert address_node["key"] == {
        "street_key": "1 rue de la paix", "city_key": "paris", "postal_code_key": "75002",
    }
    assert address_node["merge_props"] == {
        "street": "1 Rue de la Paix", "city": "Paris", "postal_code": "75002",
    }

    company_node = next(n for n in data["nodes"] if n["type"] == "Company")
    assert company_node["key"] == {"siret_key": "12345678900012"}


def test_addresses_merge_case_insensitively_on_street_city_and_postal_code():
    address_a = Address("1 Rue de la Paix", "Paris", "75002", source="Pappers", source_url="https://www.pappers.fr/entreprise/1")
    address_b = Address("1 RUE DE LA PAIX", "PARIS", "75002", source="Pappers", source_url="https://www.pappers.fr/entreprise/2")
    company_a = PapperResultSociety(
        name="ACME SARL", address=address_a, siret="12345678900012",
        creation_date="01/01/2020", link="https://www.pappers.fr/entreprise/1", directors=[],
    )
    company_b = PapperResultSociety(
        name="OTHER SARL", address=address_b, siret="98765432100099",
        creation_date="01/01/2021", link="https://www.pappers.fr/entreprise/2", directors=[],
    )

    graph = GossipGraph()
    graph.load_pappers([company_a, company_b])
    data = graph.to_graph_data()

    address_nodes = [n for n in data["nodes"] if n["type"] == "Address"]
    assert len(address_nodes) == 1
    # First-seen casing is preserved for display.
    assert address_nodes[0]["merge_props"]["street"] == "1 Rue de la Paix"


def test_persons_and_companies_merge_case_insensitively():
    address = Address("1 Rue de la Paix", "Paris", "75002", source="Pappers", source_url="https://www.pappers.fr/entreprise/1")
    person_a = Person("Jean", "Dupont", birth_date="1980-05", source="Pappers", source_url="https://www.pappers.fr/entreprise/1")
    person_b = Person("JEAN", "DUPONT", birth_date="1980-05", source="Pappers", source_url="https://www.pappers.fr/entreprise/2")
    company_a = PapperResultSociety(
        name="ACME SARL", address=address, siret="12345678900012", creation_date="01/01/2020",
        link="https://www.pappers.fr/entreprise/1", directors=[Director(person_a, "Président", "01/01/2020")],
    )
    company_b = PapperResultSociety(
        name="acme sarl", address=address, siret="12345678900012", creation_date="01/01/2020",
        link="https://www.pappers.fr/entreprise/2", directors=[Director(person_b, "Gérant", "01/01/2021")],
    )

    graph = GossipGraph()
    graph.load_pappers([company_a, company_b])
    data = graph.to_graph_data()

    person_nodes = [n for n in data["nodes"] if n["type"] == "Person"]
    company_nodes = [n for n in data["nodes"] if n["type"] == "Company"]
    assert len(person_nodes) == 1
    assert len(company_nodes) == 1
    # Same (person, company) relationship seen twice under different casing dedupes to one edge.
    director_edges = [e for e in data["edges"] if e["type"] == "DIRECTOR_OF"]
    assert len(director_edges) == 1


def test_render_html_embeds_valid_graph_data():
    graph = GossipGraph()
    graph.load_pappers(_sample_results())
    data = graph.to_graph_data()

    html = graph_html.render_html(data)

    assert "vis-network" in html
    start = html.index("const GRAPH_DATA = ") + len("const GRAPH_DATA = ")
    end = html.index(";\n", start)
    embedded = json.loads(html[start:end])
    assert embedded == data
