# Read the implementation

The code keeps the business calculation separate from transport, provider field names and storage. Every application function and method starts with a concise English docstring and has typed arguments and a return type. Local data structures and class attributes have explicit annotations; iteration targets inherit their types from those structures.

## Class responsibilities

| Class | Location | Responsibility |
| --- | --- | --- |
| `Offer` | `models.py` | Validate normalized advert fields with Pydantic; enforce dates, identifiers, role IDs and source links |
| `JobTechConnector` | `connectors.py` | Keep an injectable HTTP fetcher and declare verified workplace coverage; collect and normalize adverts |
| `EurostatConnector` | `connectors.py` | Retrieve aggregate context using a separate snapshot contract |
| `CollectionService` | `pipeline.py` | Own a database target; audit, validate and atomically publish advert collections |
| `CollectionBatch` | `contracts.py` | Carry provider records and request provenance as a frozen dataclass |
| `AdvertConnector` | `contracts.py` | Define the behaviour required of an additional advert provider |
| `PlainText` | `text.py` | Track HTML parser state and retain only visible text |

Pure calculations such as `skill_bridge` remain functions. They need no mutable object state and are easier to inspect and test directly.

## Types at each boundary

`JsonObject` is a heterogeneous dictionary used at provider JSON, SQLite and response-envelope boundaries. It deliberately contains `Any`: an annotation cannot establish that external data is truthful. Runtime validation and fixture checks provide that protection. Core stable structures use typed fields: `Offer`, `SkillMention`, `StoredSkillMention`, `BenchmarkRow`, `BenchmarkSnapshot` and catalog specifications.

The extraction contract uses `start` / `end`; the SQL and API contract preserves `start_offset` / `end_offset`. Both describe Python string indices into sanitized descriptions, with an exclusive end. The explicit mapping in `analysis.cohort` keeps persisted field names compatible.

`JsonFetcher` is a callable taking a URL and returning a JSON object. A connector accepts this callable in its constructor. Production uses the bounded HTTP client; a test supplies a local function. No network mocking framework or live credentials are needed.

## Trace a collection

1. `cli.main` parses the country, source, query list and page budget.
2. `collect_jobtech` builds the provider adapter and `CollectionService`.
3. `CollectionService.collect` checks declared coverage before any provider request and creates an audit run.
4. `JobTechConnector.collect` returns a `CollectionBatch`; `normalize` maps source fields.
5. `ingest` validates `Offer`, checks sample boundaries and dates, deduplicates and extracts evidence.
6. One transaction stores the sample and sets the run to success. A failed collection leaves the previous successful sample visible.
7. `cohort`, `describe` and `skill_bridge` calculate the view; the API exposes those same functions.

The compatibility functions `fetch_jobtech` and `fetch_benchmark` remain small, documented provider operations. The active CLI path uses the service/connector classes. There is no inheritance hierarchy joining advertisements to official economic statistics because they represent different observational units.

## Add a verified advert provider

Implement `source_id`, `supported_countries`, `collect` and `normalize` from `AdvertConnector`. Provider-specific access restrictions, mapping and pagination belong in the adapter. Country-independent validation and metrics stay in the service and analytical modules.

Before activating an adapter, document its access and reuse rules in the source register and supply small fixtures for the verified country mapping, malformed records, bounded pagination and a failed refresh. Register the provider explicitly in the CLI and coverage ledger; adding a class alone does not make it available in the interface.

## Dependency and code checks

```bash
poetry check --lock
poetry run ruff check careergraph tests scripts
poetry run mypy
poetry run pytest -q tests/test_smoke.py
```

`mypy` uses strict mode for application and startup code. Ruff checks signatures as well as ordinary code errors. The smoke test audits docstrings and typed signatures, including nested API handlers. Static checks do not prove source coverage or calculation correctness; the small data fixtures check those behaviours separately.

The complete local suite remains available through `poetry run pytest -q`. Routine CI deliberately runs only the eight selected fixture checks recorded in the current release note.
