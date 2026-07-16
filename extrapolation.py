import re
import unicodedata

COMMON_EMAIL_DOMAINS = [
    "gmail.com",
    "yahoo.com",
    "yahoo.fr",
    "hotmail.com",
    "hotmail.fr",
    "outlook.com",
    "outlook.fr",
    "icloud.com",
    "orange.fr",
    "free.fr",
    "laposte.net",
    "sfr.fr",
    "wanadoo.fr",
]


def _slug(name: str) -> str:
    """Lowercases and strips accents/non-alphanumeric characters (e.g. "Éric" -> "eric")."""
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", stripped.lower())


def _birth_years(birth_date: str | None) -> list[str]:
    if not birth_date:
        return []
    match = re.search(r"(19|20)\d{2}", birth_date)
    if not match:
        return []
    year = match.group(0)
    return [year, year[-2:]]


def generate_usernames(first_name: str, last_name: str, birth_date: str | None = None) -> list[str]:
    """
    Generates candidate usernames from a person's name and (optionally) birth date, e.g.
    "jean.dupont", "jdupont", "dupontjean1990". Order is preserved and duplicates are dropped.
    """
    fn, ln = _slug(first_name), _slug(last_name)
    if not fn or not ln:
        return []

    candidates = [
        f"{fn}{ln}",
        f"{fn}.{ln}",
        f"{fn}_{ln}",
        f"{fn}-{ln}",
        f"{ln}{fn}",
        f"{ln}.{fn}",
        f"{fn[0]}{ln}",
        f"{fn}{ln[0]}",
        f"{ln}{fn[0]}",
    ]

    for year in _birth_years(birth_date):
        candidates += [
            f"{fn}{ln}{year}",
            f"{fn}.{ln}{year}",
            f"{ln}{fn}{year}",
        ]

    seen: set[str] = set()
    out: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def generate_emails(username: str) -> list[str]:
    """Generates candidate email addresses for `username` across common email providers."""
    return [f"{username}@{domain}" for domain in COMMON_EMAIL_DOMAINS]
