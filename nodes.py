class Person:
    def __init__(self,first_name: str,last_name: str, birth_date: str|None = None, birth_place: str|None = None,
                 source: str|None = None, source_url: str|None = None):
        self.first_name = first_name
        self.last_name = last_name
        self.birth_date = birth_date
        self.birth_place = birth_place
        self.source = source
        self.source_url = source_url

class Address:
    def __init__(self,street: str,city: str,postal_code: str, source: str|None = None, source_url: str|None = None):
        self.street = street
        self.city = city
        self.postal_code = postal_code
        self.source = source
        self.source_url = source_url

class Director:
    def __init__(self, person: Person, role: str, since_date: str):
        self.person = person
        self.role = role
        self.since_date = since_date

class Email:
    def __init__(self, address: str, source: str|None = None, source_url: str|None = None):
        self.address = address
        self.source = source
        self.source_url = source_url

class OnlineAccount:
    def __init__(self, site: str, domain: str, method: str|None = None,
                 source: str|None = None, source_url: str|None = None):
        self.site = site
        self.domain = domain
        self.method = method
        self.source = source
        self.source_url = source_url