from nodes import Person, Address, Director, Email, OnlineAccount, PhoneNumber, Username
from pappers_scrapper import PapperResultSociety, PersonKey

AddressKey = tuple[str, str, str]                # normalized (street, city, postal_code)
AddressEdgeKey = tuple[str, AddressKey]          # (siret_key, addr_key)
DirectorEdgeKey = tuple[PersonKey, str]           # (person_key, siret_key)
ProbableHomeEdgeKey = tuple[AddressKey, PersonKey]
EmailKey = str                                   # normalized email address
OnlineAccountKey = tuple[str, str]               # normalized (site, domain)
RegisteredOnEdgeKey = tuple[EmailKey, OnlineAccountKey]
PhoneKey = str                                   # normalized phone number
PersonPhoneEdgeKey = tuple[PersonKey, PhoneKey]
UsernameKey = str                                # normalized username
PersonUsernameEdgeKey = tuple[PersonKey, UsernameKey]
UsernameEmailEdgeKey = tuple[UsernameKey, EmailKey]
UsernameAccountEdgeKey = tuple[UsernameKey, OnlineAccountKey]

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
        self._emails: dict[EmailKey, Email] = {}
        self._online_accounts: dict[OnlineAccountKey, OnlineAccount] = {}
        self._registered_on_edges: dict[RegisteredOnEdgeKey, tuple[Email, OnlineAccount]] = {}
        self._person_email_edges: dict[tuple[PersonKey, EmailKey], tuple[Person, Email]] = {}
        self._phones: dict[PhoneKey, PhoneNumber] = {}
        self._person_phone_edges: dict[PersonPhoneEdgeKey, tuple[Person, PhoneNumber]] = {}
        self._usernames: dict[UsernameKey, Username] = {}
        # Provided-by-user usernames (USERNAME edge) vs. guessed from name/DOB (EXTRAPOLATED_USERNAME edge)
        self._person_username_edges: dict[PersonUsernameEdgeKey, tuple[Person, Username]] = {}
        self._person_extrapolated_username_edges: dict[PersonUsernameEdgeKey, tuple[Person, Username]] = {}
        # Emails guessed from a username on a common domain (EXTRAPOLATED_EMAIL edge), not from the Person directly
        self._username_extrapolated_email_edges: dict[UsernameEmailEdgeKey, tuple[Username, Email]] = {}
        self._username_registered_on_edges: dict[UsernameAccountEdgeKey, tuple[Username, OnlineAccount]] = {}

        # Maps a normalized (first_name, last_name) to the PersonKey of the "original" Person
        # node for a --first-name/--last-name entrypoint, so load_pappers can alias-match
        # directors onto it by name alone instead of creating a second, birth-date-qualified
        # Person node.
        self._original_person_name_keys: dict[tuple[str, str], PersonKey] = {}

        # Track the original Person entrypoint and Email entrypoint(s) (if given), so that
        # once both are present we can link them regardless of which was registered first.
        self._original_person_key: PersonKey | None = None
        self._original_email_keys: set[EmailKey] = set()
        self._original_phone_key: PhoneKey | None = None
        self._original_username_keys: set[UsernameKey] = set()

    def _link_original_person_and_email(self) -> None:
        if self._original_person_key is None:
            return
        person = self._persons[self._original_person_key]
        for email_key in self._original_email_keys:
            email = self._emails[email_key]
            self._person_email_edges[(self._original_person_key, email_key)] = (person, email)

    def _link_original_person_and_phone(self) -> None:
        if self._original_person_key is None or self._original_phone_key is None:
            return
        person = self._persons[self._original_person_key]
        phone = self._phones[self._original_phone_key]
        self._person_phone_edges[(self._original_person_key, self._original_phone_key)] = (person, phone)

    def _link_original_person_and_username(self) -> None:
        if self._original_person_key is None:
            return
        person = self._persons[self._original_person_key]
        for username_key in self._original_username_keys:
            username = self._usernames[username_key]
            self._person_username_edges[(self._original_person_key, username_key)] = (person, username)

    def add_original_person(self, first_name: str, last_name: str, birth_date: str | None = None) -> None:
        """
        Registers the CLI entrypoint's own Person node, regardless of scraper results.

        Must be called before load_pappers() for this name — load_pappers consults the
        registered name key while building each director's key, so any director processed
        before this call is keyed normally and will not be retroactively merged.
        """
        fn_key, ln_key = _norm(first_name), _norm(last_name)
        person_key: PersonKey = (fn_key, ln_key, None)
        if person_key not in self._persons:
            self._persons[person_key] = Person(first_name, last_name, birth_date=birth_date, source="Provided by user")
        elif birth_date and not self._persons[person_key].birth_date:
            self._persons[person_key].birth_date = birth_date
        self._original_person_name_keys[(fn_key, ln_key)] = person_key
        self._original_person_key = person_key
        self._link_original_person_and_email()
        self._link_original_person_and_phone()
        self._link_original_person_and_username()

    def add_original_email(self, email: str) -> None:
        """Registers the CLI entrypoint's own Email node, regardless of scraper results."""
        email_key = _norm(email)
        if email_key not in self._emails:
            self._emails[email_key] = Email(email, source="Provided by user")
        self._original_email_keys.add(email_key)
        self._link_original_person_and_email()

    def add_original_phone(self, phone: str) -> None:
        """Registers the CLI entrypoint's own PhoneNumber node, regardless of scraper results."""
        phone_key = _norm(phone)
        if phone_key not in self._phones:
            self._phones[phone_key] = PhoneNumber(phone, source="Provided by user")
        self._original_phone_key = phone_key
        self._link_original_person_and_phone()

    def add_original_username(self, username: str) -> None:
        """Registers the CLI entrypoint's own Username node (user-provided, not extrapolated)."""
        username_key = _norm(username)
        if username_key not in self._usernames:
            self._usernames[username_key] = Username(username, source="Provided by user")
        self._original_username_keys.add(username_key)
        self._link_original_person_and_username()

    def add_extrapolated_username(self, username: str) -> None:
        """
        Registers a Username node guessed from the original person's name/DOB (not
        provided by the user), linked via EXTRAPOLATED_USERNAME rather than USERNAME.
        No-op if there is no original Person yet to link it to.
        """
        if self._original_person_key is None:
            return
        username_key = _norm(username)
        if username_key not in self._usernames:
            self._usernames[username_key] = Username(username, source="Extrapolated")
        person = self._persons[self._original_person_key]
        self._person_extrapolated_username_edges[(self._original_person_key, username_key)] = (
            person, self._usernames[username_key],
        )

    def add_extrapolated_email(self, username: str, email: str) -> None:
        """
        Registers an Email node guessed from a username on a common domain, linked to
        that Username via EXTRAPOLATED_EMAIL rather than the Person-level EMAIL edge —
        the email's provenance is the username, not the person directly.
        """
        username_key = _norm(username)
        if username_key not in self._usernames:
            self._usernames[username_key] = Username(username, source="Extrapolated")
        email_key = _norm(email)
        if email_key not in self._emails:
            self._emails[email_key] = Email(email, source="Extrapolated")
        self._username_extrapolated_email_edges[(username_key, email_key)] = (
            self._usernames[username_key], self._emails[email_key],
        )

    def load_phoneinfoga(self, phone: str, result: PhoneNumber) -> None:
        """Enriches the phone entrypoint's node in place with Phoneinfoga's scan result."""
        phone_key = _norm(phone)
        if phone_key not in self._phones:
            self._phones[phone_key] = result
            return
        existing = self._phones[phone_key]
        existing.country = result.country
        existing.carrier = result.carrier

    def load_holehe(self, email: str, results: list[OnlineAccount]) -> None:
        email_key = _norm(email)
        if email_key not in self._emails:
            self._emails[email_key] = Email(email)

        for account in results:
            acct_key: OnlineAccountKey = (_norm(account.site), _norm(account.domain))
            if acct_key not in self._online_accounts:
                self._online_accounts[acct_key] = account
            self._registered_on_edges[(email_key, acct_key)] = (
                self._emails[email_key], self._online_accounts[acct_key],
            )

    def load_sherlock(self, username: str, results: list[OnlineAccount]) -> None:
        self._load_username_accounts(username, results)

    def load_maigret(self, username: str, results: list[OnlineAccount]) -> None:
        self._load_username_accounts(username, results)

    def _load_username_accounts(self, username: str, results: list[OnlineAccount]) -> None:
        username_key = _norm(username)
        if username_key not in self._usernames:
            self._usernames[username_key] = Username(username)

        for account in results:
            acct_key: OnlineAccountKey = (_norm(account.site), _norm(account.domain))
            if acct_key not in self._online_accounts:
                self._online_accounts[acct_key] = account
            self._username_registered_on_edges[(username_key, acct_key)] = (
                self._usernames[username_key], self._online_accounts[acct_key],
            )

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
                name_key = (_norm(p.first_name), _norm(p.last_name))

                if name_key in self._original_person_name_keys:
                    person_key = self._original_person_name_keys[name_key]
                    original = self._persons[person_key]
                    # Enrich in place so edges already referencing this Person object
                    # (from earlier load_pappers calls) see the birth date too.
                    if p.birth_date and not original.birth_date:
                        original.birth_date = p.birth_date
                else:
                    person_key = (_norm(p.first_name), _norm(p.last_name), _norm(p.birth_date))
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

        lines.append("\n// Email nodes")
        for email_key, email in self._emails.items():
            sets = [f'e.address = "{_esc(email.address)}"']
            if email.source:
                sets.append(f'e.source = "{_esc(email.source)}"')
            if email.source_url:
                sets.append(f'e.source_url = "{_esc(email.source_url)}"')
            lines.append(
                f'MERGE (e:Email {{address_key: "{_esc(email_key)}"}}) '
                f'ON CREATE SET ' + ", ".join(sets) + ";"
            )

        lines.append("\n// OnlineAccount nodes")
        for (site_key, domain_key), account in self._online_accounts.items():
            sets = [f'oa.site = "{_esc(account.site)}"', f'oa.domain = "{_esc(account.domain)}"']
            if account.method:
                sets.append(f'oa.method = "{_esc(account.method)}"')
            if account.source:
                sets.append(f'oa.source = "{_esc(account.source)}"')
            if account.source_url:
                sets.append(f'oa.source_url = "{_esc(account.source_url)}"')
            lines.append(
                f'MERGE (oa:OnlineAccount {{site_key: "{_esc(site_key)}", domain_key: "{_esc(domain_key)}"}}) '
                f'ON CREATE SET ' + ", ".join(sets) + ";"
            )

        lines.append("\n// PhoneNumber nodes")
        for phone_key, phone in self._phones.items():
            sets = [f'ph.number = "{_esc(phone.number)}"']
            if phone.country:
                sets.append(f'ph.country = "{_esc(phone.country)}"')
            if phone.carrier:
                sets.append(f'ph.carrier = "{_esc(phone.carrier)}"')
            if phone.source:
                sets.append(f'ph.source = "{_esc(phone.source)}"')
            if phone.source_url:
                sets.append(f'ph.source_url = "{_esc(phone.source_url)}"')
            lines.append(
                f'MERGE (ph:PhoneNumber {{number_key: "{_esc(phone_key)}"}}) '
                f'ON CREATE SET ' + ", ".join(sets) + ";"
            )

        lines.append("\n// Username nodes")
        for username_key, username in self._usernames.items():
            sets = [f'u.value = "{_esc(username.value)}"']
            if username.source:
                sets.append(f'u.source = "{_esc(username.source)}"')
            if username.source_url:
                sets.append(f'u.source_url = "{_esc(username.source_url)}"')
            lines.append(
                f'MERGE (u:Username {{value_key: "{_esc(username_key)}"}}) '
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

        lines.append("\n// EMAIL edges")
        for (person_key, email_key), (person, email) in self._person_email_edges.items():
            fn_key, ln_key, bd_key = person_key
            lines.append(
                f'MATCH (p:Person {{first_name_key: "{_esc(fn_key)}", last_name_key: "{_esc(ln_key)}", birth_date_key: {_cypher_str(bd_key)}}})\n'
                f'MATCH (e:Email {{address_key: "{_esc(email_key)}"}})\n'
                f'MERGE (p)-[:EMAIL]->(e);'
            )

        lines.append("\n// PHONE edges")
        for (person_key, phone_key), (person, phone) in self._person_phone_edges.items():
            fn_key, ln_key, bd_key = person_key
            lines.append(
                f'MATCH (p:Person {{first_name_key: "{_esc(fn_key)}", last_name_key: "{_esc(ln_key)}", birth_date_key: {_cypher_str(bd_key)}}})\n'
                f'MATCH (ph:PhoneNumber {{number_key: "{_esc(phone_key)}"}})\n'
                f'MERGE (p)-[:PHONE]->(ph);'
            )

        lines.append("\n// REGISTERED_ON edges")
        for (email_key, acct_key), (email, account) in self._registered_on_edges.items():
            site_key, domain_key = acct_key
            lines.append(
                f'MATCH (e:Email {{address_key: "{_esc(email_key)}"}})\n'
                f'MATCH (oa:OnlineAccount {{site_key: "{_esc(site_key)}", domain_key: "{_esc(domain_key)}"}})\n'
                f'MERGE (e)-[:REGISTERED_ON]->(oa);'
            )

        lines.append("\n// USERNAME edges")
        for (person_key, username_key), (person, username) in self._person_username_edges.items():
            fn_key, ln_key, bd_key = person_key
            lines.append(
                f'MATCH (p:Person {{first_name_key: "{_esc(fn_key)}", last_name_key: "{_esc(ln_key)}", birth_date_key: {_cypher_str(bd_key)}}})\n'
                f'MATCH (u:Username {{value_key: "{_esc(username_key)}"}})\n'
                f'MERGE (p)-[:USERNAME]->(u);'
            )

        lines.append("\n// EXTRAPOLATED_USERNAME edges")
        for (person_key, username_key), (person, username) in self._person_extrapolated_username_edges.items():
            fn_key, ln_key, bd_key = person_key
            lines.append(
                f'MATCH (p:Person {{first_name_key: "{_esc(fn_key)}", last_name_key: "{_esc(ln_key)}", birth_date_key: {_cypher_str(bd_key)}}})\n'
                f'MATCH (u:Username {{value_key: "{_esc(username_key)}"}})\n'
                f'MERGE (p)-[:EXTRAPOLATED_USERNAME]->(u);'
            )

        lines.append("\n// EXTRAPOLATED_EMAIL edges")
        for (username_key, email_key), (username, email) in self._username_extrapolated_email_edges.items():
            lines.append(
                f'MATCH (u:Username {{value_key: "{_esc(username_key)}"}})\n'
                f'MATCH (e:Email {{address_key: "{_esc(email_key)}"}})\n'
                f'MERGE (u)-[:EXTRAPOLATED_EMAIL]->(e);'
            )

        lines.append("\n// REGISTERED_ON edges (from Username)")
        for (username_key, acct_key), (username, account) in self._username_registered_on_edges.items():
            site_key, domain_key = acct_key
            lines.append(
                f'MATCH (u:Username {{value_key: "{_esc(username_key)}"}})\n'
                f'MATCH (oa:OnlineAccount {{site_key: "{_esc(site_key)}", domain_key: "{_esc(domain_key)}"}})\n'
                f'MERGE (u)-[:REGISTERED_ON]->(oa);'
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

        for email_key, email in self._emails.items():
            nodes.append({
                "id": f"email:{email_key}",
                "type": "Email",
                "label": email.address,
                "properties": {"Address": email.address},
                "key": {"address_key": email_key},
                "merge_props": {"address": email.address},
                "source": email.source,
                "source_url": email.source_url,
            })

        for (site_key, domain_key), account in self._online_accounts.items():
            nodes.append({
                "id": f"account:{site_key}:{domain_key}",
                "type": "OnlineAccount",
                "label": account.site,
                "properties": {
                    "Site": account.site,
                    "Domain": account.domain,
                    "Method": account.method,
                },
                "key": {"site_key": site_key, "domain_key": domain_key},
                "merge_props": {
                    "site": account.site,
                    "domain": account.domain,
                    **({"method": account.method} if account.method else {}),
                },
                "source": account.source,
                "source_url": account.source_url,
            })

        for phone_key, phone in self._phones.items():
            nodes.append({
                "id": f"phone:{phone_key}",
                "type": "PhoneNumber",
                "label": phone.number,
                "properties": {
                    "Number": phone.number,
                    "Country": phone.country,
                    "Carrier": phone.carrier,
                },
                "key": {"number_key": phone_key},
                "merge_props": {
                    "number": phone.number,
                    **({"country": phone.country} if phone.country else {}),
                    **({"carrier": phone.carrier} if phone.carrier else {}),
                },
                "source": phone.source,
                "source_url": phone.source_url,
            })

        for username_key, username in self._usernames.items():
            nodes.append({
                "id": f"username:{username_key}",
                "type": "Username",
                "label": username.value,
                "properties": {"Value": username.value},
                "key": {"value_key": username_key},
                "merge_props": {"value": username.value},
                "source": username.source,
                "source_url": username.source_url,
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

        for (email_key, acct_key), (email, account) in self._registered_on_edges.items():
            site_key, domain_key = acct_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"email:{email_key}",
                "to": f"account:{site_key}:{domain_key}",
                "type": "REGISTERED_ON",
                "label": "REGISTERED_ON",
                "properties": {},
            })
            edge_id += 1

        for (person_key, email_key), (person, email) in self._person_email_edges.items():
            fn_key, ln_key, bd_key = person_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"person:{fn_key}:{ln_key}:{bd_key}",
                "to": f"email:{email_key}",
                "type": "EMAIL",
                "label": "EMAIL",
                "properties": {},
            })
            edge_id += 1

        for (person_key, phone_key), (person, phone) in self._person_phone_edges.items():
            fn_key, ln_key, bd_key = person_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"person:{fn_key}:{ln_key}:{bd_key}",
                "to": f"phone:{phone_key}",
                "type": "PHONE",
                "label": "PHONE",
                "properties": {},
            })
            edge_id += 1

        for (person_key, username_key), (person, username) in self._person_username_edges.items():
            fn_key, ln_key, bd_key = person_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"person:{fn_key}:{ln_key}:{bd_key}",
                "to": f"username:{username_key}",
                "type": "USERNAME",
                "label": "USERNAME",
                "properties": {},
            })
            edge_id += 1

        for (person_key, username_key), (person, username) in self._person_extrapolated_username_edges.items():
            fn_key, ln_key, bd_key = person_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"person:{fn_key}:{ln_key}:{bd_key}",
                "to": f"username:{username_key}",
                "type": "EXTRAPOLATED_USERNAME",
                "label": "EXTRAPOLATED_USERNAME",
                "properties": {},
            })
            edge_id += 1

        for (username_key, email_key), (username, email) in self._username_extrapolated_email_edges.items():
            edges.append({
                "id": f"e{edge_id}",
                "from": f"username:{username_key}",
                "to": f"email:{email_key}",
                "type": "EXTRAPOLATED_EMAIL",
                "label": "EXTRAPOLATED_EMAIL",
                "properties": {},
            })
            edge_id += 1

        for (username_key, acct_key), (username, account) in self._username_registered_on_edges.items():
            site_key, domain_key = acct_key
            edges.append({
                "id": f"e{edge_id}",
                "from": f"username:{username_key}",
                "to": f"account:{site_key}:{domain_key}",
                "type": "REGISTERED_ON",
                "label": "REGISTERED_ON",
                "properties": {},
            })
            edge_id += 1

        return {"nodes": nodes, "edges": edges}

    def export_html(self, path: str) -> None:
        import graph_html
        graph_html.export_html(self, path)
