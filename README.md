# Gossip Sea

**Legal & ethical notice:** This tool is for educational purposes only. By using it,
you agree to use it only for legal and ethical purposes. It's meant as a fun way to
learn OSINT techniques and to check what information about *you* is publicly
available. Do not use it to harass, stalk, or harm anyone. The author does not condone
illegal use and is not responsible for consequences arising from misuse of this tool.

Maltego on steroids — a Python OSINT pipeline that takes a name, email, phone number,
or username, runs it through a handful of public data sources, and produces a graph of
what it found. Centered on French people, since most OSINT tooling is US-centric.

## Features

- Multiple entry points: first/last name + date of birth, email address(es), phone
  number, username(s) — mix and match any combination in one run.
- Five integrated tools: [Recherche d'entreprises](https://recherche-entreprises.api.gouv.fr)
  (French company registry), [Holehe](https://github.com/megadose/holehe) (email → registered accounts),
  [Phoneinfoga](https://github.com/sundowndev/phoneinfoga) (phone → country/carrier),
  and [Sherlock](https://github.com/sherlock-project/sherlock)/[Maigret](https://github.com/soxoj/maigret)
  (username → registered accounts).
- Username/email extrapolation: guesses likely usernames from a name + birth date, and
  likely email addresses from a username across common French/international domains,
  then feeds those guesses back through Holehe/Sherlock/Maigret.
- Graph output: a Neo4j-importable Cypher script and a standalone interactive HTML
  graph, both showing every entity found and how it connects back to your inputs.

## How it works

```
CLI entrypoint (main.py)
   -> per-source scrapers (recherche_entreprises/holehe/phoneinfoga/sherlock/maigret_scraper.py)
   -> GossipGraph (graph.py) — in-memory, deduplicates by identity per node type
   -> export_cypher() -> output.cypher
   -> export_html()   -> output.html
```

Each scraper's `lookup(...)` returns a list of plain data objects (see `nodes.py`);
`main.py` feeds those into a single shared `GossipGraph`, which merges anything that
resolves to the same person/company/email/etc. and tracks where every fact came from.

## Requirements

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- A running `phoneinfoga serve` instance, reachable via the `PHONEINFOGA_URL` env var
  (default `http://localhost:5000`) — only needed if you pass `--phone`
- `sherlock` and `maigret` console scripts on `PATH` (installed automatically by
  `uv sync`, since `sherlock-project`/`maigret` are project dependencies)

## Installation

```bash
uv sync
```

Then, if you'll be looking up phone numbers, start Phoneinfoga separately, e.g. via
Docker:

```bash
docker run -p 5000:5000 sundowndev/phoneinfoga:latest serve --port 5000 -a 0.0.0.0
```

## Usage

```bash
uv run python main.py [OPTIONS]
```

| Flag | Description |
|---|---|
| `--first-name NAME` | Target's first name |
| `--last-name NAME` | Target's last name |
| `--dob DATE` | Target's date of birth (e.g. `1990-05-14`); also used to generate extrapolated usernames |
| `--email EMAIL [EMAIL ...]` | Target's email address(es) |
| `--email-file FILE` | Path to a file with one email address per line |
| `--phone PHONE` | Target's phone number |
| `--username USERNAME [USERNAME ...]` | Target's username(s) |
| `--username-file FILE` | Path to a file with one username per line |
| `-o, --output FILE` | Path for the exported Cypher file (default: `output.cypher`) |
| `--html-output FILE` | Path for the interactive HTML graph (default: `output.html`) |

Running with no arguments prints this help and exits.

### Examples

```bash
# Company/director lookup by name
uv run python main.py --first-name Jean --last-name Dupont

# Email-only: which sites is this address registered on?
uv run python main.py --email jean.dupont@example.com

# Combine everything, including username-guessing from name + DOB
uv run python main.py --first-name Jean --last-name Dupont --dob 1990-05-14 \
    --email jean.dupont@example.com --username jdupont
```

## Output

- **`output.cypher`** — a `MERGE`/`MATCH`-based Cypher script, ready to run against a
  Neo4j instance to import the graph.
- **`output.html`** — a standalone, self-contained interactive
  [vis-network](https://visjs.github.io/vis-network/) page; open it directly in a browser.

## Scraper reference

| Scraper | Input | Returns | Error type | Notes |
|---|---|---|---|---|
| Recherche d'entreprises | first/last name | `list[Company]` | `RechercheEntreprisesError` | free official gov.fr REST API, no auth or browser needed |
| Holehe | email | `list[OnlineAccount]` | *(none — per-module failures are dropped)* | async httpx, checks many site modules concurrently |
| Phoneinfoga | phone | `list[PhoneNumber]` (0 or 1) | `PhoneinfogaError` | needs an external `phoneinfoga serve` instance |
| Sherlock | username | `list[OnlineAccount]` | `SherlockError` | subprocess CLI, CSV output |
| Maigret | username | `list[OnlineAccount]` | `MaigretError` | subprocess CLI, ndjson output |
| Extrapolation | name+DOB, or username | `list[str]` | *(none — pure logic)* | no network calls; feeds guesses back into the scrapers above |

## Data model

**Nodes** (`nodes.py`): `Person`, `Address`, `Company`, `Email`, `Username`,
`OnlineAccount`, `PhoneNumber`.

**Edges** (`graph.py`): `DIRECTOR_OF`, `HAS_ADDRESS`, `PROBABLE_HOME`, `EMAIL`,
`PHONE`, `USERNAME`, `EXTRAPOLATED_USERNAME`, `EXTRAPOLATED_EMAIL`, `REGISTERED_ON`.

Every node tracks `source`/`source_url` for provenance — where a given fact came from,
and (where applicable) a link back to it.

## Development

```bash
uv run pytest
```

All scraper tests mock their external I/O boundary (httpx or subprocess), so the suite
never makes a live network/CLI call. The project is a flat
collection of scripts (no `src/` layout, no installable package) — run everything via
`uv run python main.py`.
