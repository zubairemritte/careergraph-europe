# Release 0.1 — evidence and limits

Date: **7 October 2026**. Runtime: **Python 3.12**. This is a working local first release, not a hosted production service.

## Executed verification

| Check | Observed result |
| --- | --- |
| Automated suite | **64 tests passed** |
| Static analysis | `ruff check careergraph tests scripts` passed |
| JavaScript syntax | `node --check careergraph/static/app.js` passed |
| Package installation | Editable installation built and installed successfully |
| Hosted GitHub Actions | [Run 1 passed](https://github.com/zubairemritte/careergraph-europe/actions/runs/37674475590) for implementation commit `ca7db3c92a2362983287d60eab23e0cd3094f35f` |
| Offline offer pipeline | 773 input rows → 768 accepted, 2 duplicates, 3 rejected |
| Offline extraction regression | 32 authored cases / 62 expected labels; all matched the stated contract |
| Actual JobTech collection | 317 input rows → 287 retained, 27 duplicates, 3 out-of-scope workplace countries |
| Actual Eurostat retrieval | 128 configured country/quarter cells; 108 observed values, missing cells preserved |
| API | Health, static entry page, catalog, filters, evidence, input errors, mode separation and coverage exercised through FastAPI's test client |
| Visual assets | Wide and compact SVG banners rendered for inspection |

The test client emitted a Starlette deprecation warning about its `httpx` transport. The warning did not fail the tests; the pinned test dependencies preserve the verified combination.

## Live collection audit

Source: JobTech / Arbetsförmedlingen. Workplace country: SE. Four keyword queries, at most two 100-record pages each. Full query metadata, response hashes and reconciliation counts are in [the collection audit](../examples/collection-audit.json).

| Title classification | Retained adverts |
| --- | ---: |
| Data Engineer | 64 |
| Data Analyst | 9 |
| Data Scientist | 8 |
| Analytics Engineer | 6 |
| Other / unclassified | 200 |
| **Total** | **287** |

These counts describe a collected sample and a limited title classifier. They are **not 287 confirmed data-professional vacancies**. The high unclassified share is useful evidence that source keyword matching is broad. The interface starts on the Data Analyst role to make the selected cohort explicit.

189 retained adverts contained at least one recognised description skill. This is extraction coverage, not accuracy. The `analytics engineer` query reported more matches than the configured page budget and is marked capped. Query totals overlap and are not added together.

## Official-statistics snapshot

The included [Eurostat snapshot](../examples/eurostat-context.json) covers 2024-Q3 through 2026-Q2 in the pinned NACE Rev. 2.1 series. Of 16 configured countries, **12 have an observed value for the latest displayed quarter** in this exact filtered series. CH, GB, NL and PT are unavailable in that quarter/series selection; the application does not fill them from another series.

The 128 cells are 16 countries × 8 quarters. The 108 observed values include earlier quarters and must not be confused with 108 countries. Source flags and timestamps are retained. These official rates are separate from the collected offer sample.

## Verification boundaries

- The environment's browser policy blocked loopback and local-file navigation. The application rendering and click flows were **not visually verified in a live browser**. API tests and JavaScript syntax checks are not substitutes for that check. The quickstart provides the local review path.
- Docker was unavailable in the development environment. The recipe is supplied but its build and runtime have not been executed here.
- The hosted GitHub Actions run linked above passed the lint, test and offline-reproduction steps on the implementation commit. Later commit statuses should be checked separately.
- No load test, independent real-ad annotation study, semantic model evaluation, cloud deployment or SLA has been completed.
- No offer connector beyond the verified JobTech country scope has been activated.

## What the evidence supports

The release demonstrates a reproducible ingestion-to-analysis path, typed records, conservative duplicate handling, transactional snapshots, source-aware missingness, inspectable skill calculations, a read-only API and a documented interface.

The evidence does not establish complete European offer coverage, national skill-demand estimates, general multilingual extraction accuracy, applicant suitability or causal returns from learning a skill.
