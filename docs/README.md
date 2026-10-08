# Documentation

This documentation describes the running first release. It separates implemented behaviour, measured evidence and unresolved source or modelling limits.

1. [Quickstart](quickstart.md): launch the app and reproduce a result.
2. [Product](product.md): the user problem and the release boundary.
3. [Methodology](methodology.md): what each measure means and how it is calculated.
4. [Sources](sources.md): provenance, access, reuse and actual coverage.
5. [Architecture](architecture.md): how the components fit together.
6. [Data contract](data-contract.md): field definitions and data-quality rules.
7. [Operations](operations.md): run, inspect, recover and refresh.
8. [Decisions](decisions.md): the reasoning behind important trade-offs.
9. [Code guide](code-guide.md): class responsibilities, types and extension contracts.
10. [Release 0.2](release-0.2.md): small checks for the Poetry and typing update.
11. [Release 0.1](release-0.1.md): dated initial collection evidence and original verification.

For code navigation, start at `careergraph/cli.py`, follow collection into `connectors.py` and `pipeline.py`, then read `analysis.py`. The UI uses the same API responses that the tests exercise.
