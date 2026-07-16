"""Shared plumbing for scrapers that shell out to a console script (Sherlock, Maigret)
and parse a report file it writes to a temp directory."""
import os
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlparse

# Some site names these CLIs report can include non-ASCII characters; on Windows a
# captured pipe defaults to the console codepage (cp1252) instead of UTF-8 and would
# crash the subprocess with a UnicodeEncodeError unless forced here.
SUBPROCESS_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def domain(url: str) -> str:
    """Returns a URL's netloc with any leading 'www.' stripped."""
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


@contextmanager
def run_cli_producing_file(
    build_command, output_filename: str, error_cls: type[Exception], tool_name: str, subject: str
) -> Iterator[str]:
    """
    Creates a temp directory, runs `build_command(tmp_dir)` (an argv list, typically
    pointing the CLI's own --folderoutput at tmp_dir), and yields the path to
    `output_filename` inside that directory. The temp directory stays alive for the
    duration of the `with` block so the caller can parse the file before cleanup.

    Raises `error_cls` if the process exits non-zero or the expected output file is
    missing, with a message of the form "<tool_name> failed/produced no output for
    <subject>".
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        command = build_command(tmp_dir)
        try:
            subprocess.run(command, capture_output=True, text=True, check=True, env=SUBPROCESS_ENV)
        except subprocess.CalledProcessError as e:
            raise error_cls(f"{tool_name} failed for {subject}: {e.stderr}") from e

        output_path = os.path.join(tmp_dir, output_filename)
        if not os.path.exists(output_path):
            raise error_cls(f"{tool_name} produced no output for {subject}")

        yield output_path
