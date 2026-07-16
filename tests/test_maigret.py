import json
import os
import subprocess
from unittest.mock import patch

import pytest

import maigret_scraper
from nodes import OnlineAccount


def _folderoutput(args):
    return args[args.index("--folderoutput") + 1]


def _write_ndjson(tmp_dir, username, entries):
    path = os.path.join(tmp_dir, f"report_{username}_ndjson.json")
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_lookup_maps_ndjson_entries_to_online_accounts():
    def fake_run(args, **kwargs):
        _write_ndjson(_folderoutput(args), "torvalds", [
            {"sitename": "GitHub", "url_main": "https://www.github.com/",
             "status": {"url": "https://github.com/torvalds"}},
        ])
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("cli_scraper_utils.subprocess.run", side_effect=fake_run):
        results = maigret_scraper.lookup("torvalds")

    assert len(results) == 1
    assert all(isinstance(r, OnlineAccount) for r in results)
    assert results[0].site == "GitHub"
    assert results[0].domain == "github.com"
    assert results[0].source == "Maigret"
    assert results[0].source_url == "https://github.com/torvalds"


def test_lookup_raises_maigret_error_on_cli_failure():
    def fake_run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, output="", stderr="network error")

    with patch("cli_scraper_utils.subprocess.run", side_effect=fake_run):
        with pytest.raises(maigret_scraper.MaigretError):
            maigret_scraper.lookup("torvalds")


def test_lookup_raises_maigret_error_when_output_file_missing():
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("cli_scraper_utils.subprocess.run", side_effect=fake_run):
        with pytest.raises(maigret_scraper.MaigretError):
            maigret_scraper.lookup("torvalds")
