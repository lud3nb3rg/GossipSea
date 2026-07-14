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
            sets = []
            if p.birth_place:
                sets.append(f'p.birth_place = "{_esc(p.birth_place)}"')
            if p.source:
                sets.append(f'p.source = "{_esc(p.source)}"')
            if p.source_url:
                sets.append(f'p.source_url = "{_esc(p.source_url)}"')
            if sets:
                line += "\n  ON CREATE SET " + ", ".join(sets)
            lines.append(line + ";")

        lines.append("\n// Address nodes")
        for (street, city, postal_code), addr in self._addresses.items():
            sets = [f'a.city = "{_esc(city)}"']
            if addr.source:
                sets.append(f'a.source = "{_esc(addr.source)}"')
            if addr.source_url:
                sets.append(f'a.source_url = "{_esc(addr.source_url)}"')
            lines.append(
                f'MERGE (a:Address {{street: "{_esc(street)}", postal_code: "{_esc(postal_code)}"}}) '
                f'ON CREATE SET ' + ", ".join(sets) + ";"
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

    def to_graph_data(self) -> dict:
        """Build a JSON-serializable {"nodes": [...], "edges": [...]} structure for the interactive HTML export."""
        nodes: list[dict] = []
        edges: list[dict] = []

        for (fn, ln, bd), p in self._persons.items():
            nodes.append({
                "id": f"person:{fn}:{ln}:{bd}",
                "type": "Person",
                "label": f"{fn} {ln}",
                "properties": {
                    "First name": p.first_name,
                    "Last name": p.last_name,
                    "Birth date": p.birth_date,
                    "Birth place": p.birth_place,
                },
                "key": {"first_name": fn, "last_name": ln, "birth_date": bd},
                "merge_props": {"birth_place": p.birth_place} if p.birth_place else {},
                "source": p.source,
                "source_url": p.source_url,
            })

        for (street, city, postal_code), addr in self._addresses.items():
            nodes.append({
                "id": f"addr:{street}:{postal_code}",
                "type": "Address",
                "label": f"{street}\n{postal_code} {city}",
                "properties": {
                    "Street": addr.street,
                    "City": addr.city,
                    "Postal code": addr.postal_code,
                },
                "key": {"street": street, "postal_code": postal_code},
                "merge_props": {"city": city},
                "source": addr.source,
                "source_url": addr.source_url,
            })

        for siret, company in self._companies.items():
            nodes.append({
                "id": f"company:{siret}",
                "type": "Company",
                "label": company.name,
                "properties": {
                    "Name": company.name,
                    "SIRET": company.siret,
                    "Creation date": company.creation_date,
                    "Link": company.link,
                },
                "key": {"siret": siret},
                "merge_props": {"name": company.name, "creation_date": company.creation_date, "link": company.link},
                "source": "Pappers",
                "source_url": company.link,
            })

        edge_id = 0
        for company, address in self._address_edges.values():
            edges.append({
                "id": f"e{edge_id}",
                "from": f"company:{company.siret}",
                "to": f"addr:{address.street}:{address.postal_code}",
                "type": "HAS_ADDRESS",
                "label": "HAS_ADDRESS",
                "properties": {},
            })
            edge_id += 1

        for person, company, director in self._director_edges.values():
            edges.append({
                "id": f"e{edge_id}",
                "from": f"person:{person.first_name}:{person.last_name}:{person.birth_date}",
                "to": f"company:{company.siret}",
                "type": "DIRECTOR_OF",
                "label": director.role,
                "properties": {"role": director.role, "since_date": director.since_date},
            })
            edge_id += 1

        return {"nodes": nodes, "edges": edges}

    def export_html(self, path: str) -> None:
        import graph_html
        graph_html.export_html(self, path)
