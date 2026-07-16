# Identity key for a Person: normalized (first_name, last_name, birth_date). Recherche
# d'entreprises-parsed directors build this from the API's raw name fields (only empty
# birth_date -> None), while graph.py builds it via its own `_norm()` (lowercased/stripped)
# — same shape, not interchangeable outside graph.py's normalization.
PersonKey = tuple[str, str, str | None]


class Person:
    """A natural person. Distinct Person nodes are deduplicated by PersonKey in graph.py."""
    def __init__(self,first_name: str,last_name: str, birth_date: str|None = None, birth_place: str|None = None,
                 source: str|None = None, source_url: str|None = None):
        self.first_name = first_name
        self.last_name = last_name
        self.birth_date = birth_date
        self.birth_place = birth_place
        self.source = source
        self.source_url = source_url

class Address:
    """A street address, e.g. a company's registered address or a probable home address."""
    def __init__(self,street: str,city: str,postal_code: str, source: str|None = None, source_url: str|None = None):
        self.street = street
        self.city = city
        self.postal_code = postal_code
        self.source = source
        self.source_url = source_url

class Director:
    """Edge payload (not a standalone graph node) carrying a Person's role and start date
    on a given Company, for the DIRECTOR_OF relationship."""
    def __init__(self, person: Person, role: str, since_date: str):
        self.person = person
        self.role = role
        self.since_date = since_date

class Company:
    """A company from the Recherche d'entreprises French company registry, with its directors."""
    def __init__(self, name: str, address: Address, siret: str, creation_date: str, link: str,
                 directors: list[Director], legal_form: str | None = None):
        self.name = name
        self.address = address
        self.siret = siret
        self.creation_date = creation_date
        self.link = link
        self.directors = directors
        self.legal_form = legal_form

    def __str__(self):
        return (f"Company(name={self.name}, address={self.address}, siret={self.siret}, "
                f"creation_date={self.creation_date}, link={self.link}, legal_form={self.legal_form})")

class Email:
    """An email address, either user-provided or extrapolated from a username."""
    def __init__(self, address: str, source: str|None = None, source_url: str|None = None):
        self.address = address
        self.source = source
        self.source_url = source_url

class Username:
    """A username, either user-provided or extrapolated from a name/date of birth."""
    def __init__(self, value: str, source: str|None = None, source_url: str|None = None):
        self.value = value
        self.source = source
        self.source_url = source_url

class OnlineAccount:
    """An account found on a given site by a username/email search (Holehe/Sherlock/Maigret)."""
    def __init__(self, site: str, domain: str, method: str|None = None,
                 source: str|None = None, source_url: str|None = None):
        self.site = site
        self.domain = domain
        self.method = method
        self.source = source
        self.source_url = source_url

class PhoneNumber:
    """A phone number, optionally enriched with country/carrier data from Phoneinfoga."""
    def __init__(self, number: str, country: str|None = None, carrier: str|None = None,
                 source: str|None = None, source_url: str|None = None):
        self.number = number
        self.country = country
        self.carrier = carrier
        self.source = source
        self.source_url = source_url