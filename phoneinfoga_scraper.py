import os
from urllib.parse import quote

import httpx

from nodes import PhoneNumber

DEFAULT_BASE_URL = os.environ.get("PHONEINFOGA_URL", "http://localhost:5000")


class PhoneinfogaError(Exception):
    """Raised when the Phoneinfoga REST API is unreachable or returns an error."""


def lookup(phone: str, base_url: str = DEFAULT_BASE_URL) -> list[PhoneNumber]:
    """
    Registers `phone` with a running `phoneinfoga serve` instance and returns a
    single-item list containing a PhoneNumber populated from its "local" scanner
    (always-on, no API key required): country and carrier as statically parsed from
    the number itself. Returns a list, like every other scraper's lookup(), even
    though there's only ever one result on success; raises PhoneinfogaError on failure.
    """
    try:
        with httpx.Client(base_url=base_url, timeout=30.0) as client:
            client.post("/api/v2/numbers", json={"number": phone}).raise_for_status()
            response = client.get(f"/api/v2/numbers/{quote(phone, safe='')}/scan/results")
            response.raise_for_status()
    except httpx.HTTPError as e:
        raise PhoneinfogaError(f"Phoneinfoga request failed: {e}") from e

    local = response.json().get("local", {})
    return [PhoneNumber(
        phone,
        country=local.get("country"),
        carrier=local.get("carrier"),
        source="Phoneinfoga",
    )]
