from nodes import Person, Address, Director
from pappers_scrapper import PapperResultSociety, PersonKey

AddressKey = tuple[str, str, str]                # normalized (street, city, postal_code)
AddressEdgeKey = tuple[str, AddressKey]          # (siret_key, addr_key)
DirectorEdgeKey = tuple[PersonKey, str]           # (person_key, siret_key)
ProbableHomeEdgeKey = tuple[AddressKey, PersonKey]

# Legal forms (normalized) under which a company's registered address is treated as the
# director's probable home address, rather than a business premises.
_PROBABLE_HOME_LEGAL_FORMS = {
    "entrepreneur individuel",
    "sci, société civile immobilière",
}


def _esc(s: str | None) -> str:
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _cypher_str(s: str | None) -> str:
    """Returns a Cypher string literal, or null for None."""
    return f'"{_esc(s)}"' if s is not None else "null"


def _norm(s: str | None) -> str | None:
    """Normalizes a string for case-insensitive identity matching, preserving None."""
    return s.strip().lower() if s is not None else None


class GossipGraph:
    def __init__(self) -> None:
        self._companies: dict[str, PapperResultSociety] = {}
        self._persons: dict[PersonKey, Person] = {}
        self._addresses: dict[AddressKey, Address] = {}
        # Dicts instead of lists to deduplicate across multiple load_pappers() calls
        self._address_edges: dict[AddressEdgeKey, tuple[PapperResultSociety, Address]] = {}
        self._director_edges: dict[DirectorEdgeKey, tuple[Person, PapperResultSociety, Director]] = {}
        self._probable_home_edges: dict[ProbableHomeEdgeKey, tuple[Address, Person]] = {}

    def load_pappers(self, results: list[PapperResultSociety]) -> None:
        for company in results:
            siret_key = _norm(company.siret)
            self._companies[siret_key] = company

            addr_key: AddressKey = (
                _norm(company.address.street),
                _norm(company.address.city),
                _norm(company.address.postal_code),
            )
            if addr_key not in self._addresses:
                self._addresses[addr_key] = company.address
            self._address_edges[(siret_key, addr_key)] = (company, self._addresses[addr_key])

            is_probable_home = _norm(company.legal_form) in _PROBABLE_HOME_LEGAL_FORMS

            for director in company.directors:
                p = director.person
                person_key: PersonKey = (_norm(p.first_name), _norm(p.last_name), _norm(p.birth_date))
                if person_key not in self._persons:
                    self._persons[person_key] = p
                self._director_edges[(person_key, siret_key)] = (self._persons[person_key], company, director)
                if is_probable_home:
                    self._probable_home_edges[(addr_key, person_key)] = (
                        self._addresses[addr_key], self._persons[person_key],
                    )

    def export_cypher(self, path: str) -> None:
        lines: list[str] = []

        lines.append("// Person nodes")
        for (fn_key, ln_key, bd_key), p in self._persons.items():
            line = (
                f'MERGE (p:Person {{first_name_key: "{_esc(fn_key)}", last_name_key: "{_esc(ln_key)}", birth_date_key: {_cypher_str(bd_key)}}})'
            )
            sets = [f'p.first_name = "{_esc(p.first_name)}"', f'p.last_name = "{_esc(p.last_name)}"']
            if p.birth_date:
                sets.append(f'p.birth_date = "{_esc(p.birth_date)}"')
            if p.birth_place:
                sets.append(f'p.birth_place = "{_esc(p.birth_place)}"')
            if p.source:
                sets.append(f'p.source = "{_esc(p.source)}"')
            if p.source_url:
                sets.append(f'p.source_url = "{_esc(p.source_url)}"')
            line += "\n  ON CREATE SET " + ", ".join(sets)
            lines.append(line + ";")

        lines.append("\n// Address nodes")
        for (street_key, city_key, postal_key), addr in self._addresses.items():
            sets = [
                f'a.street = "{_esc(addr.street)}"',
                f'a.city = "{_esc(addr.city)}"',
                f'a.postal_code = "{_esc(addr.postal_code)}"',
            ]
            if addr.source:
                sets.append(f'a.source = "{_esc(addr.source)}"')
            if addr.source_url:
                sets.append(f'a.source_url = "{_esc(addr.source_url)}"')
            lines.append(
                f'MERGE (a:Address {{street_key: "{_esc(street_key)}", city_key: "{_esc(city_key)}", postal_code_key: "{_esc(postal_key)}"}}) '
                f'ON CREATE SET ' + ", ".join(sets) + ";"
            )

        lines.append("\n// Company nodes")
        for siret_key, company in self._companies.items():
            sets = [
                f'c.siret = "{_esc(company.siret)}"',
                f'c.name = "{_esc(company.name)}"',
                f'c.creation_date = "{_esc(company.creation_date)}"',
                f'c.link = "{_esc(company.link)}"',
            ]
            if company.legal_form:
                sets.append(f'c.legal_form = "{_esc(company.legal_form)}"')
            lines.append(
                f'MERGE (c:Company {{siret_key: "{_esc(siret_key)}"}}) '
                f'ON CREATE SET ' + ", ".join(sets) + ";"
            )

        lines.append("\n// HAS_ADDRESS edges")
        for (siret_key, addr_key), (company, address) in self._address_edges.items():
            street_key, city_key, postal_key = addr_key
            lines.append(
                f'MATCH (c:Company {{siret_key: "{_esc(siret_key)}"}})\n'
                f'MATCH (a:Address {{street_key: "{_esc(street_key)}", city_key: "{_esc(city_key)}", postal_code_key: "{_esc(postal_key)}"}}) \n'
                f'MERGE (c)-[:HAS_ADDRESS]->(a);'
            )

        lines.append("\n// DIRECTOR_OF edges")
        for (person_key, siret_key), (person, company, director) in self._director_edges.items():
            fn_key, ln_key, bd_key = person_key
            lines.append(
                f'MATCH (p:Person {{first_name_key: "{_esc(fn_key)}", last_name_key: "{_esc(ln_key)}", birth_date_key: {_cypher_str(bd_key)}}})\n'
                f'MATCH (c:Company {{siret_key: "{_esc(siret_key)}"}})\n'
                f'MERGE (p)-[:DIRECTOR_OF {{role: "{_esc(director.role)}", since_date: "{_esc(director.since_date)}"}}]->(c);'
            )

        lines.append("\n// PROBABLE_HOME edges")
        for (addr_key, person_key), (address, person) in self._probable_home_edges.items():
            street_key, city_key, postal_key = addr_key
            fn_key, ln_key, bd_key = person_key
            lines.append(
                f'MATCH (a:Address {{street_key: "{_esc(street_key)}", city_key: "{_esc(city_key)}", postal_code_key: "{_esc(postal_key)}"}})\n'
                f'MATCH (p:Person {{first_name_key: "{_esc(fn_key)}", last_name_key: "{_esc(ln_key)}", birth_date_key: {_cypher_str(bd_key)}}})\n'
                f'MERGE (a)-[:PROBABLE_HOME]->(p);'
            )

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def to_graph_data(self) -> dict:
        """Build a JSON-serializable {"nodes": [...], "edges": [...]} structure for the interactive HTML export."""
        nodes: list[dict] = []
        edges: list[dict] = []

        for (fn_key, ln_key, bd_key), p in self._persons.items():
            nodes.append({
                "id": f"person:{fn_key}:{ln_key}:{bd_key}",
                "type": "Person",
                "label": f"{p.first_name} {p.last_name}",
                "properties": {
                    "First name": p.first_name,
                    "Last name": p.last_name,
                    "Birth date": p.birth_date,
                    "Birth place": p.birth_place,
                },
                "key": {"first_name_key": fn_key, "last_name_key": ln_key, "birth_date_key": bd_key},
                "merge_props": {
                    "first_name": p.first_name,
                    "last_name": p.last_name,
                    **({"birth_date": p.birth_date} if p.birth_date else {}),
                    **({"birth_place": p.birth_place} if p.birth_place else {}),
                },
                "source": p.source,
                "source_url": p.source_url,
            })

        for (street_key, city_key, postal_key), addr in self._addresses.items():
            nodes.append({
                "id": f"addr:{street_key}:{city_key}:{postal_key}",
                "type": "Address",
                "label": f"{addr.street}\n{addr.postal_code} {addr.city}",
                "properties": {
                    "Street": addr.street,
                    "City": addr.city,
                    "Postal code": addr.postal_code,
                },
                "key": {"street_key": street_key, "city_key": city_key, "postal_code_key": postal_key},
                "merge_props": {"street": addr.street, "city": addr.city, "postal_code": addr.postal_code},
                "source": addr.source,
                "source_url": addr.source_url,
            })

        for siret_key, company in self._companies.items():
            nodes.append({
                "id": f"company:{siret_key}",
                "type": "Company",
                "label": company.name,
                "properties": {
                    "Name": company.name,
                    "SIRET": company.siret,
                    "Legal form": company.legal_form,
                    "Creation date": company.creation_date,
                    "Link": company.link,
                },
                "key": {"siret_key": siret_key},
                "merge_props": {
                    "siret": company.siret,
                    "name": company.name,
                    "creation_date": company.creation_date,
                    "link": company.link,
                    **({"legal_form": company.legal_form} if company.legal_form else {}),
                },
                "source": "Pappers",
                "source_url": company.link,
            })

        edge_id = 0
        for (siret_key, addr_key), (company, address) in self._address_edges.items():
            street_key, city_key, postal_key = addr_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"company:{siret_key}",
                "to": f"addr:{street_key}:{city_key}:{postal_key}",
                "type": "HAS_ADDRESS",
                "label": "HAS_ADDRESS",
                "properties": {},
            })
            edge_id += 1

        for (person_key, siret_key), (person, company, director) in self._director_edges.items():
            fn_key, ln_key, bd_key = person_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"person:{fn_key}:{ln_key}:{bd_key}",
                "to": f"company:{siret_key}",
                "type": "DIRECTOR_OF",
                "label": director.role,
                "properties": {"role": director.role, "since_date": director.since_date},
            })
            edge_id += 1

        for (addr_key, person_key), (address, person) in self._probable_home_edges.items():
            street_key, city_key, postal_key = addr_key
            fn_key, ln_key, bd_key = person_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"addr:{street_key}:{city_key}:{postal_key}",
                "to": f"person:{fn_key}:{ln_key}:{bd_key}",
                "type": "PROBABLE_HOME",
                "label": "PROBABLE_HOME",
                "properties": {},
            })
            edge_id += 1

        return {"nodes": nodes, "edges": edges}

    def export_html(self, path: str) -> None:
        import graph_html
        graph_html.export_html(self, path)
