# Quickstart: from checkout to an explainable result

## 1. Install

Use Python 3.12 and Git. No cloud account, database server or API secret is needed for the first release.

```bash
git clone https://github.com/zubairemritte/careergraph-europe.git
cd careergraph-europe
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
```

On Windows PowerShell, create the environment with `py -3.12 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`. If activation is restricted, invoke `.venv\Scripts\python.exe` directly in place of `python`; changing the system execution policy is unnecessary.

An editable installation means changes in this checkout are immediately used when you run the package. The lock files record the versions used for release verification.

## 2. Build the offline demonstration

```bash
python -m careergraph demo
python -m careergraph benchmark --from-file examples/eurostat-context.json
```

The first command should report **773 input records, 768 accepted offers, 2 duplicates and 3 rejected records**. The extra rows deliberately exercise duplicate, invalid, future and expired-record handling.

The offers are fictional. The second command loads a genuine, dated Eurostat snapshot already included in the repository. It does not make a network request.

The SQLite database is created at `data/careergraph.db`. This directory is excluded from Git. Nothing is uploaded.

## 3. Open the application

```bash
python -m careergraph serve
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
python -m careergraph collect --source jobtech --country SE --pages 2
```

This runs four default keyword queries, with at most two 100-record pages per query. Overlapping results are deduplicated. The source's reported query totals must not be added together.

The verified connector currently accepts workplaces in Sweden. `--country DE` does not silently collect Swedish jobs or change the country label: it stops with a clear error.

Custom queries are explicit and recorded:

```bash
python -m careergraph collect --country SE --query "data analyst" --query "dataanalytiker" --pages 2
```

The latest successful collection for a source/country replaces the **current analytical sample**, while earlier successful runs remain in the database. Changing the query set changes the sample. It is not an incremental merge with old results.

Select **Collected offers** in the interface. Choose the relevant role family: keyword search may return many titles that the classifier marks **Other / unclassified**.

## 5. Refresh official context

```bash
python -m careergraph benchmark
```

The connector requests the latest eight quarters of the pinned Eurostat series. A new snapshot is stored only after the dimensions and values pass validation. Unsupported or missing country/quarter values remain null.

To make a new dated public-statistics export:

```bash
python -m careergraph benchmark --export data/eurostat-context-latest.json
```

## 6. Reproduce a result without the browser

```bash
python -m careergraph inspect --mode demo --country DE --role data_analyst --skills python,sql
python -m careergraph coverage
python -m careergraph evaluate
python -m pytest -q
```

The JSON output includes the selected sample, skill counts, one-skill gains, co-occurrence relationships and collection records. API documentation is at `/docs`; its JSON specification is at `/openapi.json`.

## Common problems

| Symptom | Meaning / action |
| --- | --- |
| `No module named careergraph` | Run from the repository root or install with `python -m pip install --no-deps -e .`. |
| `No module named fastapi` | Use the project's virtual environment and install the lock file. |
| Port 8000 is busy | Run `python -m careergraph serve --port 8001`, then open port 8001. |
| No live offers for a country | Its connector may not exist or no successful collection has run. Check `coverage`. |
| Zero offers after filtering | This is an empty *sample*, not a claim that no jobs exist. Clear the date/role filters. |
| Source returns 429 or a longer retry delay | The run stops safely. Respect the provider's delay before trying again. |
| Source schema changes | The connector rejects the response. Review the contract rather than force-loading it. |
| Benchmark value is unavailable | The pinned series contains no value for that country and period. Do not substitute zero. |

## Separate databases

The database option comes **before** the command:

```bash
python -m careergraph --db data/research.db demo
python -m careergraph --db data/research.db serve --port 8001
```

This is useful for keeping an experiment separate from an existing demonstration.
