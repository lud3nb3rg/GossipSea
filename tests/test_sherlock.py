import csv
import os
import subprocess
from unittest.mock import patch

import pytest

import sherlock_scraper
from nodes import OnlineAccount


def _folderoutput(args):
    return args[args.index("--folderoutput") + 1]


def _write_csv(tmp_dir, username, rows):
    path = os.path.join(tmp_dir, f"{username}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["username", "name", "url_main", "url_user", "exists"])
        writer.writeheader()
        writer.writerows(rows)


def test_lookup_returns_only_claimed_accounts():
    def fake_run(args, **kwargs):
        _write_csv(_folderoutput(args), "torvalds", [
            {"username": "torvalds", "name": "GitHub", "url_main": "https://www.github.com/",
             "url_user": "https://github.com/torvalds", "exists": "Claimed"},
            {"username": "torvalds", "name": "Reddit", "url_main": "https://www.reddit.com/",
             "url_user": "https://reddit.com/user/torvalds", "exists": "Not Claimed"},
        ])
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("cli_scraper_utils.subprocess.run", side_effect=fake_run):
        results = sherlock_scraper.lookup("torvalds")

    assert len(results) == 1
    assert all(isinstance(r, OnlineAccount) for r in results)
    assert results[0].site == "GitHub"
    assert results[0].domain == "github.com"
    assert results[0].source == "Sherlock"
    assert results[0].source_url == "https://github.com/torvalds"


def test_lookup_raises_sherlock_error_on_cli_failure():
    def fake_run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, output="", stderr="network error")

    with patch("cli_scraper_utils.subprocess.run", side_effect=fake_run):
        with pytest.raises(sherlock_scraper.SherlockError):
            sherlock_scraper.lookup("torvalds")


def test_lookup_raises_sherlock_error_when_output_file_missing():
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("cli_scraper_utils.subprocess.run", side_effect=fake_run):
        with pytest.raises(sherlock_scraper.SherlockError):
            sherlock_scraper.lookup("torvalds")
