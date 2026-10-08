# Quickstart: from checkout to an explainable result

## 1. Install with Poetry

Use Python 3.12, Git and Poetry 2.5.1. Python support is deliberately restricted to the validated 3.12 series. No cloud account or source credentials are needed.

Install Poetry in its own environment, outside the project. Choose one operating-system block.

**macOS / Linux** (Python 3.12 already installed):

```bash
python3.12 -m venv "$HOME/careergraph-tools"
"$HOME/careergraph-tools/bin/python" -m pip install poetry==2.5.1
export PATH="$HOME/careergraph-tools/bin:$PATH"
```

**Windows PowerShell** (Python 3.12 already installed):

```powershell
py -3.12 -m venv "$env:USERPROFILE\careergraph-tools"
& "$env:USERPROFILE\careergraph-tools\Scripts\python.exe" -m pip install poetry==2.5.1
$env:Path = "$env:USERPROFILE\careergraph-tools\Scripts;$env:Path"
```

The PATH command applies to the current terminal. Repeat it in a new terminal, or invoke Poetry using the full path above with `poetry` in place of `python`. See the [official installation documentation](https://python-poetry.org/docs/#installation) for other supported installation methods.

From either operating system:

```bash
poetry --version
git clone https://github.com/zubairemritte/careergraph-europe.git
cd careergraph-europe
poetry env use 3.12
poetry sync
poetry check --lock
poetry run pytest -q tests/test_smoke.py
```

Poetry creates `.venv` and installs the project in editable mode. Direct dependency versions live in `pyproject.toml`; `poetry.lock` pins transitive versions and distribution hashes. Use `poetry sync` after pulling an update. Dependency upgrades require an intentional change and a new reviewed lock, not a routine `poetry update` during setup.

The five smoke checks use tiny fixtures and temporary databases. They make no public-API requests and do not generate the full synthetic dataset. The following sections are the full local exploration path, run explicitly when ready.

## 2. Build the offline demonstration

```bash
poetry run careergraph demo
poetry run careergraph benchmark --from-file examples/eurostat-context.json
```

The first command should report **773 input records, 768 accepted offers, 2 duplicates and 3 rejected records**. The extra rows deliberately exercise duplicate, invalid, future and expired-record handling.

The offers are fictional. The second command loads a genuine, dated Eurostat snapshot already included in the repository. It does not make a network request.

The SQLite database is created at `data/careergraph.db`. This directory is excluded from Git. Nothing is uploaded.

## 3. Open the application

```bash
poetry run careergraph serve
```

Open `http://127.0.0.1:8000` in your browser. Keep the terminal running. Press `Ctrl+C` there to stop the server.

In the interface:

1. Keep **Illustrative demo** selected and choose a country.
2. Choose **Data Analyst** or another role family.
3. Inspect the denominator beside each skill: an offer is counted once per skill.
4. Edit the selected skills in **One skill further**.
5. Click an additional-skill result to see exactly which offers it affects.
6. Expand an offer to read the snippets.
7. Inspect **Coverage** to distinguish configured filters from collected feeds.

Changing a country in demo mode demonstrates software behaviour; it does not establish that country's real skill demand.

## 4. Collect actual offers

```bash
poetry run careergraph collect --source jobtech --country SE --pages 2
```

This runs four default keyword queries, with at most two 100-record pages per query. Overlapping results are deduplicated. The source's reported query totals must not be added together.

The verified connector currently accepts workplaces in Sweden. `--country DE` does not silently collect Swedish jobs or change the country label: it stops with a clear error.

Custom queries are explicit and recorded:

```bash
poetry run careergraph collect --country SE --query "data analyst" --query "dataanalytiker" --pages 2
```

The latest successful collection for a source/country replaces the **current analytical sample**, while earlier successful runs remain in the database. Changing the query set changes the sample. It is not an incremental merge with old results.

Select **Collected offers** in the interface. Choose the relevant role family: keyword search may return many titles that the classifier marks **Other / unclassified**.

## 5. Refresh official context

```bash
poetry run careergraph benchmark
```

The connector requests the latest eight quarters of the pinned Eurostat series. A new snapshot is stored only after the dimensions and values pass validation. Unsupported or missing country/quarter values remain null.

To make a new dated public-statistics export:

```bash
poetry run careergraph benchmark --export data/eurostat-context-latest.json
```

## 6. Reproduce a result without the browser

```bash
poetry run careergraph inspect --mode demo --country DE --role data_analyst --skills python,sql
poetry run careergraph coverage
poetry run careergraph evaluate
poetry run pytest -q
```

The JSON output includes the selected sample, skill counts, one-skill gains, co-occurrence relationships and collection records. API documentation is at `/docs`; its JSON specification is at `/openapi.json`.

## Common problems

| Symptom | Meaning / action |
| --- | --- |
| `No module named careergraph` | Run from the repository root, run `poetry sync`, and use `poetry run careergraph`. |
| `No module named fastapi` | Run `poetry sync` and execute the command through `poetry run`. |
| Port 8000 is busy | Run `poetry run careergraph serve --port 8001`, then open port 8001. |
| No live offers for a country | Its connector may not exist or no successful collection has run. Check `coverage`. |
| Zero offers after filtering | This is an empty *sample*, not a claim that no jobs exist. Clear the date/role filters. |
| Source returns 429 or a longer retry delay | The run stops safely. Respect the provider's delay before trying again. |
| Source schema changes | The connector rejects the response. Review the contract rather than force-loading it. |
| Benchmark value is unavailable | The pinned series contains no value for that country and period. Do not substitute zero. |

## Separate databases

The database option comes **before** the command:

```bash
poetry run careergraph --db data/research.db demo
poetry run careergraph --db data/research.db serve --port 8001
```

This is useful for keeping an experiment separate from an existing demonstration.
