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
    assert person_node["key"] == {"first_name": "Jean", "last_name": "Dupont", "birth_date": "1980-05"}
    assert person_node["merge_props"] == {"birth_place": "Paris"}

    address_node = next(n for n in data["nodes"] if n["type"] == "Address")
    assert address_node["source"] == "Pappers"
    assert address_node["merge_props"] == {"city": "Paris"}

    company_node = next(n for n in data["nodes"] if n["type"] == "Company")
    assert company_node["key"] == {"siret": "12345678900012"}


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
