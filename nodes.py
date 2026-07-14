class Person:
    def __init__(self,first_name: str,last_name: str, birth_date: str|None = None, birth_place: str|None = None):
        self.first_name = first_name
        self.last_name = last_name
        self.birth_date = birth_date
        self.birth_place = birth_place

class Address:
    def __init__(self,street: str,city: str,postal_code: str):
        self.street = street
        self.city = city
        self.postal_code = postal_code

class Director:
    def __init__(self, person: Person, role: str, since_date: str):
        self.person = person
        self.role = role
        self.since_date = since_date