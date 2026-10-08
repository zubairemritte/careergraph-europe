# Release 0.2 - readable code and a Poetry environment

Date: **8 October 2026**. Python support: **3.12 only**. This update improves implementation clarity and reproducibility; it does not add new live country feeds.

## Changes

- Concise English docstrings and typed signatures for all 68 application functions and methods, including nested API handlers and transport protocols.
- Explicit local structures and class attributes; stable shared catalog, evidence and benchmark contracts.
- `JobTechConnector`, `EurostatConnector`, `CollectionService`, `CollectionBatch` and an injectable `AdvertConnector` protocol. Pure analytical formulas remain functions.
- Poetry 2.5.1; exact direct dependency constraints and a generated `poetry.lock` with transitive versions and distribution hashes. The former requirements locks are removed.
- Strict mypy configuration, signature lint checks and small fixture checks in automatic CI.
- Public code navigation, Poetry installation instructions and updated architecture documentation.
- Existing SQLite tables and evidence API field names are retained. No database migration is required for a 0.1 database.

## Executed checks for this update

| Check | Result |
| --- | --- |
| Small dataset and calculation checks | **8 passed**; no live API requests or full demo generation |
| Tiny ingestion fixture | 4 records -> 2 accepted, 1 duplicate, 1 unverified-country rejection |
| Failed-refresh fixture | Previous one-record successful sample remains visible; latest failure is exposed |
| API evidence | One missing-dbt advert reconciles with the bridge result; stored evidence offsets identify the matched text |
| Official-series fixture | Sparse missing cells and provisional flags retained with reordered axes |
| Function contract audit | Application functions have docstrings and typed signatures |
| Strict types | `mypy`: no issues in 16 source files |
| Dependencies | `poetry sync` and `poetry check --lock` succeeded |
| Packaging | Poetry built the wheel and sdist; wheel includes configuration, SQL and static interface assets |

Ruff lint is part of the same verification path. The test client still emits the inherited Starlette warning about the `httpx` transport; it does not fail these checks. This update preserves the tested dependency combination rather than introducing another transport migration.

## Execution boundary

The full suite, 768-offer synthetic pipeline, live collection, benchmark refresh, browser server and Docker build were **not executed for this update**. The full local commands remain available in the quickstart. Routine CI runs only lint, strict types and the eight selected fixture checks.

The [0.1 evidence](release-0.1.md) records the earlier full verification and dated source collection. Its 64-test result describes that implementation commit, not a new full-suite run of 0.2. The previously reported local browser and Docker verification limitations still apply.

Current actual offer coverage remains one verified official provider/workplace scope. The country catalog and the source register remain separate, and official economy-wide statistics remain separate from skill-demand calculations.
