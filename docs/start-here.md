# Start here: one entry point, five responsibilities

Use the command line first. You do not have to construct the project's classes to run it:

```bash
poetry run careergraph --help
poetry run careergraph doctor
```

`doctor` checks the installed runtime, bundled files and SQLite support without creating a filesystem database or contacting a provider. The [compatibility note](compatibility.md) explains its limits and the tested environment profiles.

## Read four entry points first

| Order | Open | Find | The question it answers |
| --- | --- | --- | --- |
| 1 | [`cli.py`](../careergraph/cli.py) | `main` | Which operation did the user request? |
| 2 | [`pipeline.py`](../careergraph/pipeline.py) | `CollectionService.collect` | How does a collection become a safe current sample? |
| 3 | [`connectors.py`](../careergraph/connectors.py) | `JobTechConnector.collect`, then `normalize` | How does one provider become normalized advert fields? |
| 4 | [`analysis.py`](../careergraph/analysis.py) | `skill_bridge` | What does the additional-skill result actually count? |

Follow `ingest` only after understanding the collection service. Follow `cohort` only after understanding the metric. Detailed HTTP interfaces and dictionary schemas are a second reading, not additional workflows to learn.

## Where each responsibility belongs

| Responsibility | Owning files | Keep changes here |
| --- | --- | --- |
| Commands | `cli.py` | Arguments, command dispatch and installation diagnosis |
| Source access | `connectors.py`, `http.py` | Provider mappings, request budgets and HTTP policy |
| Validated storage | `pipeline.py`, `models.py`, `db.py`, `sql/schema.sql` | Audit lifecycle, validation, transactions and tables |
| Analysis | `analysis.py`, `text.py`, `catalog.py`, `config/` | Sample selection, calculations, evidence and matching rules |
| Presentation | `api.py`, `static/` | Read-only HTTP responses and the English interface |

`demo.py` and `evaluation.py` are explicit utilities. `contracts.py` describes shared data shapes and interfaces. It contains no independent ingestion or calculation engine.

## The few classes that matter first

| Name | Kind | What one instance keeps | Who creates it? |
| --- | --- | --- | --- |
| `JobTechConnector` | Operational adapter | A provider fetcher; verified coverage is declared on the class | The collection entry function |
| `EurostatConnector` | Operational adapter | A separate official-statistics fetcher | The benchmark CLI branch |
| `CollectionService` | Operational service | One local database path | The collection entry function |
| `Offer` | Validated data model | The fields of one normalized advert | `ingest`, through `model_validate` |

These names describe four different jobs, not four interchangeable ways to collect data. The two source adapters keep their retrieval implementation inside their methods. The service owns publication; it does not translate provider fields. The model checks actual values; it does not fetch or store them.

Other class declarations are supporting structures:

- `CollectionBatch` is a record-and-audit container.
- `TypedDict` declarations describe dictionary fields; ordinary callers do not need to instantiate them.
- `AdvertConnector`, `ResponseReader` and `Opener` are type-checking interfaces, not services to run.
- `PlainText` is the internal stateful parser behind `clean_text`.

## Follow one advert

The command calls `collect_jobtech`, which constructs the adapter and service. The service checks declared country coverage before retrieval. The adapter returns a `CollectionBatch` and normalizes each hit. `ingest` validates an `Offer`, removes conservative duplicates, extracts evidence and commits a successful sample. Analysis selects that sample; the API displays the same calculations.

The functions `fetch_jobtech`, `normalize_jobtech` and `fetch_benchmark` are compatibility shortcuts for the adapter methods. Existing imports remain valid. New collection code should follow the class methods above; no provider algorithm is duplicated in the shortcuts.

## Choose a change by its purpose

| You want to change… | Start at… |
| --- | --- |
| A search query or page budget | CLI arguments; source-specific limits remain in the adapter |
| A provider field mapping or verified country | `JobTechConnector.normalize` and the source register |
| A skill alias | `config/skills.json` and its regression cases |
| The one-skill calculation | `analysis.skill_bridge` and the hand-calculated test |
| Rejected/duplicate handling | `pipeline.ingest` and a tiny authored fixture |
| A label or page layout | `static/`, without duplicating a calculation in JavaScript |

Each function docstring now explains inputs and outputs. Functions that access files, databases or providers also state their side effects; expected errors are documented where relevant. Read the function's contract before following its helpers. The [complete function index](function-index.md) links every definition to its owner.
