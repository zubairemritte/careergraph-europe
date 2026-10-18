# Dependency compatibility and validation scope

The supported interpreter is **64-bit CPython 3.12**. Python 3.11, 3.13+, PyPy and 32-bit installations are not claimed as supported by this release. Keep Poetry **2.5.1** in its own tool environment; it creates the project's separate `.venv`.

## What is pinned

| Layer | Exact direct versions | Reason |
| --- | --- | --- |
| API | FastAPI 0.142.2; Starlette 1.7.0 | Preserve the working API combination |
| Validation | Pydantic 2.13.5 | Validate actual normalized records |
| Server | Uvicorn 0.54.0 | Keep the basic server installation; no optional native server extras |
| Requirement metadata | packaging 26.3 | Parse standard dependency declarations in the installation diagnostic |
| Test transport | HTTPX2 2.13.1 | Use the transport supported by the pinned Starlette test client |
| Development | pytest 9.1.1; Ruff 0.16.10; mypy 2.4.0 | Repeat the same bounded checks |
| Build | poetry-core 2.5.0 | Preserve the package build backend |

`pyproject.toml` declares these pins. `poetry.lock` contains the complete transitive solution, distribution hashes and platform markers, including Windows-only dependencies where required. Do not copy a Linux `pip freeze` into another operating system or run a general update during setup.

## Install and check

```bash
poetry env use 3.12
poetry sync
poetry check --lock
poetry run python -m pip check
poetry run careergraph doctor
```

The resolver checks declared package constraints. `pip check` checks the installed dependencies against their metadata. `doctor` checks the actual interpreter, direct runtime versions, bundled resources and an in-memory SQLite window-function query. It creates no filesystem database and makes no source request. These checks complement small behaviour tests; none is an absolute proof against every possible runtime failure.

## Automated profiles

The [workflow](../.github/workflows/ci.yml) installs the same lock and runs static checks plus **ten small fixture/installation tests** on:

| Profile | Runner | Architecture |
| --- | --- | --- |
| Linux | Ubuntu 24.04 | x64 |
| Windows | Windows Server 2022 | x64 |
| macOS Apple Silicon | macOS 14 | arm64 |
| macOS Intel | macOS 15 | x64 |

[GitHub Actions](https://github.com/zubairemritte/careergraph-europe/actions) records the results for each actual commit. A successful run demonstrates those profiles, not every historical version of those operating systems. In particular, a Windows hosted-runner result is not a test of every Windows desktop installation.

## macOS details

Use a Python build native to your Mac's processor. `uname -m` reports `arm64` for Apple Silicon or `x86_64` for Intel; `sw_vers` shows the operating-system version. Follow the official Python installer instructions, including the supplied certificate setup if HTTPS validation fails. Do not disable TLS verification to work around a certificate problem.

Project text reads explicitly use UTF-8 where files can contain non-ASCII text. Filesystem paths use `pathlib`; no Unix-only server acceleration package is required. Older macOS releases, Windows on ARM and other unlisted profiles need their own validation before support is claimed.

## Execution boundary

The automated checks use tiny authored records and temporary databases. They do not generate the complete demo, collect live adverts, refresh an external benchmark, run a browser session or build/run Docker. External APIs, local permissions, occupied ports and local OS/library differences can still produce errors; the source and operations documents explain diagnosis and recovery.

Official references: [Poetry locked installs](https://python-poetry.org/docs/basic-usage/), [GitHub hosted-runner profiles](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [Starlette test client](https://starlette.dev/testclient/), [HTTPX2 distribution](https://pypi.org/project/httpx2/2.13.1/).
