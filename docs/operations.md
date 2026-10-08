# Operations and recovery

## Supported execution path

The validated path is a local Python 3.12 virtual environment. Collection commands write SQLite snapshots; the read-only server presents them. There are no hidden scheduled jobs or paid cloud services.

```bash
poetry run careergraph demo
poetry run careergraph benchmark --from-file examples/eurostat-context.json
poetry run careergraph serve
```

## Refresh actual sources

Run the offer collector, inspect its report, then refresh official context independently:

```bash
poetry run careergraph collect --country SE --pages 2
poetry run careergraph benchmark
poetry run careergraph coverage
```

Changing keyword queries changes the next current sample. Record the same query configuration when comparing repeated runs. A bounded search cannot prove that an offer absent from a later sample was closed.

## HTTP failure policy

- Per-request timeout: 25 seconds.
- Maximum attempts: three for transient transport failures or HTTP 429/500/502/503/504.
- Numeric or HTTP-date `Retry-After` is respected when it fits the ten-second retry budget; a longer requested delay stops the run rather than retrying too early.
- Invalid JSON, unexpected response shape, non-transient HTTP errors and series-contract changes fail explicitly.
- Response size is capped at 10 MB per request.
- Collection errors do not publish a partial offer snapshot.

A hard process termination can leave a `running` record. It remains invisible to analysis. Investigate the interrupted process before starting another run; no automatic resume is claimed.

## Inspect a run with SQL

```sql
SELECT source, kind, country, status, started_at, completed_at
FROM runs
ORDER BY started_at DESC;

SELECT country, role, COUNT(*) AS retained_offers
FROM offers
WHERE run_id = :run_id
GROUP BY country, role
ORDER BY country, role;

SELECT skill, COUNT(*) AS adverts_mentioning_skill
FROM skill_mentions
WHERE run_id = :run_id
GROUP BY skill
ORDER BY adverts_mentioning_skill DESC;
```

Use the run identifier printed by the CLI. Do not sum all historical runs to measure a current offer sample.

## Freshness

The UI shows the publication window and collection records. A live collection older than 48 hours receives a stale indicator. This is a display rule, not an automatic refresh guarantee. Offers can expire or be removed after collection; the source link is the authority for current application status.

The benchmark displays its official quarter and retrieval date. It is not described as today's vacancy rate. A failed benchmark refresh leaves the previously stored official snapshot intact.

## Back up a database

Stop the application and collector before copying the database and any WAL files, or use SQLite's online backup API to obtain a consistent copy:

```python
import sqlite3

with sqlite3.connect("data/careergraph.db") as source:
    with sqlite3.connect("data/careergraph-backup.db") as destination:
        source.backup(destination)
```

Databases contain collected offer text. Keep backups out of Git. No destructive cleanup command runs automatically in this release; retention must be chosen when sustained collection begins.

## Tests and CI

```bash
poetry run pytest -q
poetry run ruff check careergraph tests
poetry run careergraph evaluate
```

Tests use fixtures and temporary databases; they do not depend on source availability. Automatic CI runs strict type checking, lint and eight small fixture checks only. It does not run the full demo, full test suite or live collection. The full test command above is for explicit local validation.

```bash
poetry check --lock
poetry run mypy
poetry run pytest -q tests/test_smoke.py
```

The authored extraction regression report is useful for detecting changed behaviour. It must not be marketed as 100% accuracy on real multilingual adverts.

## Container recipe

```bash
docker build -t careergraph-europe .
docker run --rm -p 127.0.0.1:8000:8000 -v careergraph-data:/app/data careergraph-europe
```

The container initializes the demo and bundled official snapshot only when the database is absent. Existing data is preserved. The runtime user is non-root. The release report states whether the Docker path was executed in the development environment.

The app is designed for a trusted local user. Exposing it as a public service requires a separate deployment review, bounded concurrency, monitoring, source-refresh ownership and appropriate controls for retained text. The repository does not claim these are already in place.
