import json

from cli_scraper_utils import domain, run_cli_producing_file
from nodes import OnlineAccount


class MaigretError(Exception):
    """Raised when the Maigret CLI fails or produces unparseable output."""


def lookup(username: str, timeout: float = 30.0) -> list[OnlineAccount]:
    """
    Runs the Maigret CLI against `username` and returns one OnlineAccount per site
    where the username was found ("Claimed"). Requires the `maigret` console script
    (installed via the maigret dependency) to be on PATH. Recursive/derived-username
    extraction is disabled so results stay scoped to the requested username.

    (Maigret's default timeout is tuned lower than Sherlock's 60s default — the two
    were adjusted independently against each tool's own typical run time, not something
    that needs to be kept in sync.)
    """
    with run_cli_producing_file(
        lambda tmp_dir: [
            "maigret", username,
            "-J", "ndjson",
            "--folderoutput", tmp_dir,
            "--timeout", str(timeout),
            "--no-recursion", "--no-extracting",
            "--no-progressbar", "--no-color",
        ],
        f"report_{username}_ndjson.json",
        MaigretError,
        "Maigret",
        repr(username),
    ) as json_path:
        accounts: list[OnlineAccount] = []
        with open(json_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                # Maigret's own report writer (maigret/report.py: generate_json_report)
                # already skips every site whose status != CLAIMED before writing a
                # line, for both "json" and "ndjson" report types. So, unlike
                # Sherlock's CSV (which lists every checked site) or Holehe's raw
                # per-module dicts, every line here is already a positive match — no
                # additional exists/status filter is needed.
                accounts.append(OnlineAccount(
                    site=entry.get("sitename"),
                    domain=domain(entry.get("url_main", "")),
                    method="username_search",
                    source="Maigret",
                    source_url=entry.get("status", {}).get("url"),
                ))

    return accounts
