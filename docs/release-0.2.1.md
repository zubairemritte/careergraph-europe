# Release 0.2.1 - code navigation and compatibility checks

Date: **18 October 2026**. Application version: **0.2.1**. This release improves code readability and installation verification without changing the analytical definitions, SQLite schema or verified source coverage.

## Changes

- Function contracts describe each argument and return value, with errors, side effects and examples where relevant. The small contract test checks named inputs and return explanations.
- Each source adapter owns its actual collection/normalization implementation. Original function imports remain as small compatibility shortcuts.
- The start page groups the code by five responsibilities and identifies four entry points to read first. A function index links every definition to its owner.
- `careergraph doctor` reports the interpreter, exact direct runtime versions, SQLite capability and bundled files without creating a database or contacting a provider.
- HTTPX2 2.13.1 replaces the deprecated HTTPX test transport. The working API/server/model versions stay pinned; packaging 26.3 is an explicit dependency of the standard requirement-metadata diagnostic.
- UTF-8 file reads are explicit in the application, container initializer and regression-case loader.
- The CI matrix validates the lock and ten bounded checks on Linux x64, Windows x64, macOS arm64 and macOS Intel. Hosted results are attached to the implementation commit in GitHub Actions.

## Verification

The local verification path is `poetry check --lock`, `pip check`, `careergraph doctor`, Ruff, strict mypy and the ten selected fixture/installation checks. The dataset fixture still has four input records, two accepted adverts, one duplicate and one rejected country. Added installation checks cover a successful read-only diagnosis and a nonzero exit for mismatched package versions.

The four hosted profiles and their exact scope are listed in [compatibility](compatibility.md). Consult the Actions result for the specific implementation commit before claiming a hosted profile passed. The historical 0.1/0.2 reports remain dated evidence for their own implementations.

The full suite, complete synthetic pipeline, external collection, real browser flow and Docker build/run are left for explicit local execution. No personal guide or learning notes belong to the public repository.
