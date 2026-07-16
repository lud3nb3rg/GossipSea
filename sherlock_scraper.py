import csv

from cli_scraper_utils import domain, run_cli_producing_file
from nodes import OnlineAccount


class SherlockError(Exception):
    """Raised when the Sherlock CLI fails or produces unparseable output."""


def lookup(username: str, timeout: float = 60.0) -> list[OnlineAccount]:
    """
    Runs the Sherlock CLI against `username` and returns one OnlineAccount per site
    where the username was found ("Claimed"). Requires the `sherlock` console script
    (installed via the sherlock-project dependency) to be on PATH.
    """
    with run_cli_producing_file(
        lambda tmp_dir: [
            "sherlock", username,
            "--csv", "--no-txt",
            "--folderoutput", tmp_dir,
            "--timeout", str(timeout),
        ],
        f"{username}.csv",
        SherlockError,
        "Sherlock",
        repr(username),
    ) as csv_path:
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    return [
        OnlineAccount(
            site=row["name"],
            domain=domain(row["url_main"]),
            method="username_search",
            source="Sherlock",
            source_url=row["url_user"],
        )
        for row in rows
        if row.get("exists") == "Claimed"
    ]
