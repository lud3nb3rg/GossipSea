import csv
import os
import subprocess
import tempfile
from urllib.parse import urlparse

from nodes import OnlineAccount

# Some site names Sherlock reports can include non-ASCII characters; on Windows a
# captured pipe defaults to the console codepage (cp1252) instead of UTF-8 and would
# crash the subprocess with a UnicodeEncodeError unless forced here.
_SUBPROCESS_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


class SherlockError(Exception):
    """Raised when the Sherlock CLI fails or produces unparseable output."""


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def lookup(username: str, timeout: float = 60.0) -> list[OnlineAccount]:
    """
    Runs the Sherlock CLI against `username` and returns one OnlineAccount per site
    where the username was found ("Claimed"). Requires the `sherlock` console script
    (installed via the sherlock-project dependency) to be on PATH.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            subprocess.run(
                [
                    "sherlock", username,
                    "--csv", "--no-txt",
                    "--folderoutput", tmp_dir,
                    "--timeout", str(timeout),
                ],
                capture_output=True, text=True, check=True, env=_SUBPROCESS_ENV,
            )
        except subprocess.CalledProcessError as e:
            raise SherlockError(f"Sherlock failed for {username!r}: {e.stderr}") from e

        csv_path = os.path.join(tmp_dir, f"{username}.csv")
        if not os.path.exists(csv_path):
            raise SherlockError(f"Sherlock produced no output for {username!r}")

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    return [
        OnlineAccount(
            site=row["name"],
            domain=_domain(row["url_main"]),
            method="username_search",
            source="Sherlock",
            source_url=row["url_user"],
        )
        for row in rows
        if row.get("exists") == "Claimed"
    ]
