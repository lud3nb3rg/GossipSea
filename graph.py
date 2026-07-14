import networkx as nx
import matplotlib.pyplot as plt

from nodes import Person, Address, Director
from pappers_scrapper import PapperResultSociety, PersonKey

AddressKey = tuple[str, str, str]
AddressEdgeKey = tuple[str, AddressKey]          # (siret, addr_key)
DirectorEdgeKey = tuple[PersonKey, str]           # (person_key, siret)


def _esc(s: str | None) -> str:
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _cypher_str(s: str | None) -> str:
    """Returns a Cypher string literal, or null for None."""
    return f'"{_esc(s)}"' if s is not None else "null"


class GossipGraph:
    def __init__(self) -> None:
        self._companies: dict[str, PapperResultSociety] = {}
        self._persons: dict[PersonKey, Person] = {}
        self._addresses: dict[AddressKey, Address] = {}
        # Dicts instead of lists to deduplicate across multiple load_pappers() calls
        self._address_edges: dict[AddressEdgeKey, tuple[PapperResultSociety, Address]] = {}
        self._director_edges: dict[DirectorEdgeKey, tuple[Person, PapperResultSociety, Director]] = {}

    def load_pappers(self, results: list[PapperResultSociety]) -> None:
        for company in results:
            self._companies[company.siret] = company

            addr_key: AddressKey = (company.address.street, company.address.city, company.address.postal_code)
            if addr_key not in self._addresses:
                self._addresses[addr_key] = company.address
            self._address_edges[(company.siret, addr_key)] = (company, self._addresses[addr_key])

            for director in company.directors:
                p = director.person
                person_key: PersonKey = (p.first_name, p.last_name, p.birth_date)
                if person_key not in self._persons:
                    self._persons[person_key] = p
                self._director_edges[(person_key, company.siret)] = (self._persons[person_key], company, director)

    def export_cypher(self, path: str) -> None:
        lines: list[str] = []

        lines.append("// Person nodes")
        for (fn, ln, bd), p in self._persons.items():
            line = (
                f'MERGE (p:Person {{first_name: "{_esc(fn)}", last_name: "{_esc(ln)}", birth_date: {_cypher_str(bd)}}})'
            )
            if p.birth_place:
                line += f'\n  ON CREATE SET p.birth_place = "{_esc(p.birth_place)}"'
            lines.append(line + ";")

        lines.append("\n// Address nodes")
        for (street, city, postal_code), addr in self._addresses.items():
            lines.append(
                f'MERGE (a:Address {{street: "{_esc(street)}", postal_code: "{_esc(postal_code)}"}}) '
                f'ON CREATE SET a.city = "{_esc(city)}";'
            )

        lines.append("\n// Company nodes")
        for company in self._companies.values():
            lines.append(
                f'MERGE (c:Company {{siret: "{_esc(company.siret)}"}}) '
                f'ON CREATE SET c.name = "{_esc(company.name)}", '
                f'c.creation_date = "{_esc(company.creation_date)}", '
                f'c.link = "{_esc(company.link)}";'
            )

        lines.append("\n// HAS_ADDRESS edges")
        for company, address in self._address_edges.values():
            lines.append(
                f'MATCH (c:Company {{siret: "{_esc(company.siret)}"}})\n'
                f'MATCH (a:Address {{street: "{_esc(address.street)}", postal_code: "{_esc(address.postal_code)}"}}) \n'
                f'MERGE (c)-[:HAS_ADDRESS]->(a);'
            )

        lines.append("\n// DIRECTOR_OF edges")
        for person, company, director in self._director_edges.values():
            lines.append(
                f'MATCH (p:Person {{first_name: "{_esc(person.first_name)}", last_name: "{_esc(person.last_name)}", birth_date: {_cypher_str(person.birth_date)}}})\n'
                f'MATCH (c:Company {{siret: "{_esc(company.siret)}"}})\n'
                f'MERGE (p)-[:DIRECTOR_OF {{role: "{_esc(director.role)}", since_date: "{_esc(director.since_date)}"}}]->(c);'
            )

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def display(self) -> None:
        G = nx.MultiDiGraph()

        node_colors: dict[str, str] = {}

        for (fn, ln, bd), _ in self._persons.items():
            node_id = f"person:{fn}:{ln}:{bd}"
            label = f"{fn} {ln}"
            G.add_node(node_id, label=label)
            node_colors[node_id] = "#6baed6"  # blue

        for (street, city, postal_code) in self._addresses:
            node_id = f"addr:{street}:{postal_code}"
            label = f"{street}\n{postal_code} {city}"
            G.add_node(node_id, label=label)
            node_colors[node_id] = "#fd8d3c"  # orange

        for siret, company in self._companies.items():
            node_id = f"company:{siret}"
            G.add_node(node_id, label=company.name)
            node_colors[node_id] = "#74c476"  # green

        for company, address in self._address_edges.values():
            G.add_edge(f"company:{company.siret}", f"addr:{address.street}:{address.postal_code}", label="HAS_ADDRESS")

        for person, company, director in self._director_edges.values():
            person_id = f"person:{person.first_name}:{person.last_name}:{person.birth_date}"
            G.add_edge(person_id, f"company:{company.siret}", label=director.role)

        pos = nx.spring_layout(G, seed=42, k=2)
        labels = nx.get_node_attributes(G, "label")
        colors = [node_colors[n] for n in G.nodes()]
        edge_labels = {(u, v): d["label"] for u, v, d in G.edges(data=True)}

        plt.figure(figsize=(14, 9))
        nx.draw(G, pos, labels=labels, node_color=colors, node_size=2000,
                font_size=8, arrows=True, arrowsize=15,
                edge_color="#888888", width=1.5, connectionstyle="arc3,rad=0.1")
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7)

        legend = [
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#6baed6", markersize=12, label="Person"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#74c476", markersize=12, label="Company"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#fd8d3c", markersize=12, label="Address"),
        ]
        plt.legend(handles=legend, loc="upper left")
        plt.title("GossipSea — OSINT Graph")
        plt.tight_layout()
        plt.show()
