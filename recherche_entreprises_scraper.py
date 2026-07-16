import httpx

from nodes import Person, Address, Director, Company, PersonKey

BASE_URL = "https://recherche-entreprises.api.gouv.fr"

# INSEE "nature juridique" codes (level III of the nomenclature, see
# https://www.insee.fr/fr/information/2028129) mapped to a human-readable label, for the
# handful of legal forms most commonly seen among individual-linked companies. Codes not
# in this table fall back to the raw numeric code rather than failing.
_LEGAL_FORM_LABELS: dict[str, str] = {
    "1000": "Entrepreneur individuel",
    "5202": "Société en nom collectif",
    "5306": "Société en commandite simple",
    "5385": "Société en commandite par actions",
    "5410": "SARL nationale",
    "5498": "SARL unipersonnelle (EURL)",
    "5499": "Société à responsabilité limitée (SARL)",
    "5505": "SA à conseil d'administration",
    "5510": "SA nationale à conseil d'administration",
    "5515": "SA à directoire",
    "5710": "Société par actions simplifiée (SAS)",
    "5720": "Société par actions simplifiée unipersonnelle (SASU)",
    "6220": "Groupement d'intérêt économique (GIE)",
    "6540": "Société civile immobilière (SCI)",
    "9220": "Association déclarée",
}


class RechercheEntreprisesError(Exception):
    """Raised when the Recherche d'entreprises API is unreachable or returns an error."""


def _legal_form_label(code: str | None) -> str | None:
    if not code:
        return None
    return _LEGAL_FORM_LABELS.get(code, code)


def _format_street(siege: dict) -> str:
    parts = [siege.get("numero_voie"), siege.get("indice_repetition"), siege.get("type_voie"), siege.get("libelle_voie")]
    street = " ".join(p for p in parts if p)
    return street or siege.get("adresse") or ""


def _extract_directors(dirigeants: list[dict], person_registry: dict[PersonKey, Person], source_url: str) -> list[Director]:
    directors = []
    for d in dirigeants:
        # "personne morale" entries are companies acting as director (e.g. a holding),
        # not natural persons — skip them, same as the old Pappers scraper did.
        if d.get("type_dirigeant") != "personne physique":
            continue
        first_name = (d.get("prenoms") or "").strip()
        last_name = (d.get("nom") or "").strip()
        if not first_name and not last_name:
            continue
        birth_date = d.get("date_de_naissance") or d.get("annee_de_naissance") or None
        role = d.get("qualite") or ""
        key: PersonKey = (first_name, last_name, birth_date)
        if key not in person_registry:
            person_registry[key] = Person(first_name, last_name, birth_date=birth_date,
                                           source="Recherche d'entreprises", source_url=source_url)
        # The API doesn't expose when a director took office (Pappers scraped that from
        # its page; there's no equivalent field here), so since_date is always empty.
        directors.append(Director(person_registry[key], role, ""))
    return directors


def _parse_company(entry: dict, person_registry: dict[PersonKey, Person]) -> Company:
    siege = entry.get("siege") or {}
    siren = entry.get("siren", "")
    link = f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"

    address = Address(
        _format_street(siege),
        siege.get("libelle_commune") or "",
        siege.get("code_postal") or "",
        source="Recherche d'entreprises",
        source_url=link,
    )
    directors = _extract_directors(entry.get("dirigeants") or [], person_registry, link)
    name = entry.get("nom_complet") or entry.get("nom_raison_sociale") or ""

    return Company(
        name,
        address,
        siege.get("siret") or "",
        entry.get("date_creation") or "",
        link,
        directors,
        legal_form=_legal_form_label(entry.get("nature_juridique")),
    )


def lookup(first_name: str, last_name: str) -> list[Company]:
    """
    Looks up `first_name last_name` as a company director via the Recherche
    d'entreprises API (https://recherche-entreprises.api.gouv.fr) and returns a
    Company per matching enterprise, each with its registered address and directors
    inline — unlike the old Pappers scraper, the search response already contains
    everything needed, so there's no separate per-company page to fetch.
    """
    results: list[Company] = []
    person_registry: dict[PersonKey, Person] = {}
    params = {
        "prenoms_personne": first_name,
        "nom_personne": last_name,
        "type_personne": "dirigeant",
        "per_page": 25,
    }

    try:
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            page = 1
            total_pages = 1
            while page <= total_pages:
                response = client.get("/search", params={**params, "page": page})
                response.raise_for_status()
                payload = response.json()
                total_pages = payload.get("total_pages", 1)
                for entry in payload.get("results", []):
                    results.append(_parse_company(entry, person_registry))
                page += 1
    except httpx.HTTPError as e:
        raise RechercheEntreprisesError(f"Recherche d'entreprises request failed: {e}") from e

    return results
