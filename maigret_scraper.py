import json
import os
import subprocess
import tempfile
from urllib.parse import urlparse

from nodes import OnlineAccount

# Maigret prints unicode characters (e.g. a donation banner) to stdout/stderr; on
# Windows, a captured pipe defaults to the console codepage (cp1252) instead of
# UTF-8 and crashes the subprocess with a UnicodeEncodeError unless forced here.
_SUBPROCESS_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


class MaigretError(Exception):
    """Raised when the Maigret CLI fails or produces unparseable output."""


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def lookup(username: str, timeout: float = 30.0) -> list[OnlineAccount]:
    """
    Runs the Maigret CLI against `username` and returns one OnlineAccount per site
    where the username was found ("Claimed"). Requires the `maigret` console script
    (installed via the maigret dependency) to be on PATH. Recursive/derived-username
    extraction is disabled so results stay scoped to the requested username.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            subprocess.run(
                [
                    "maigret", username,
                    "-J", "ndjson",
                    "--folderoutput", tmp_dir,
                    "--timeout", str(timeout),
                    "--no-recursion", "--no-extracting",
                    "--no-progressbar", "--no-color",
                ],
                capture_output=True, text=True, check=True, env=_SUBPROCESS_ENV,
            )
        except subprocess.CalledProcessError as e:
            raise MaigretError(f"Maigret failed for {username!r}: {e.stderr}") from e

        json_path = os.path.join(tmp_dir, f"report_{username}_ndjson.json")
        if not os.path.exists(json_path):
            raise MaigretError(f"Maigret produced no output for {username!r}")

        accounts: list[OnlineAccount] = []
        with open(json_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                accounts.append(OnlineAccount(
                    site=entry.get("sitename"),
                    domain=_domain(entry.get("url_main", "")),
                    method="username_search",
                    source="Maigret",
                    source_url=entry.get("status", {}).get("url"),
                ))

    return accounts
