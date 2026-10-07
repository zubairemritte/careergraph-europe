# Architecture decisions

## 001 — Country is configuration, not connector identity

**Decision:** use ISO alpha-2 in the analytical model, and maintain a separate country/source coverage record.

**Reason:** a European product can share formulas and UI while providers have different country semantics, access rules and actual coverage. A dropdown must not create the illusion of available data.

**Consequence:** additional countries can be configured without changing the scoring logic, but a live connector must still demonstrate permitted access and correct workplace mapping.

## 002 — Begin with accessible, attributable sources

**Decision:** implement JobTech for advertisements and Eurostat for aggregate context. Defer restricted EURES extraction and Adzuna analytics until suitable access is established.

**Reason:** a reproducible public portfolio needs a credible source path, not an undocumented endpoint or an unlicensed dataset.

**Consequence:** real offer coverage begins in one verified market while the product's model and demonstration span Europe. This limitation is visible.

## 003 — Use SQLite for the first release

**Decision:** keep normalized snapshots, matches and audit metadata in a transactional local database.

**Reason:** a reviewer can reproduce the project without provisioning a warehouse. The release workload is a bounded sample; local transactions and inspectable SQL are sufficient.

**Consequence:** horizontal scaling and many concurrent writers are out of scope. Move to a warehouse or service database when measured workload and integration requirements justify it, retaining the current data contract.

## 004 — Prefer an explainable extraction baseline

**Decision:** use a versioned dictionary, limited role aliases and stored evidence spans before introducing semantic models.

**Reason:** error analysis and denominator discipline should exist before model complexity. The baseline is deterministic, cheap to run and inspectable.

**Consequence:** negation, optional requirements, unknown skills and ambiguous product names remain limitations. A reviewed real-ad evaluation set is required before claiming multilingual accuracy or replacing this baseline.

## 005 — Report marginal skill coverage, not a composite career score

**Decision:** count additional sampled adverts whose detected skills become covered after one addition.

**Reason:** this answers a concrete question and reconciles exactly with visible evidence. A combined country/salary/employability score would add unsupported assumptions.

**Consequence:** this is not a measure of skill mastery or hiring probability, and it ignores requirements that are not detected skills. The interface says so.

## 006 — Retain observations, never infer closure from disappearance

**Decision:** append successful collection snapshots and select the latest successful run for analysis.

**Reason:** keyword search is bounded and mutable. A missing advert in a later result is not sufficient evidence that the vacancy closed.

**Consequence:** historical comparisons require identical collection settings and source/vocabulary review. Vacancy duration and closure analysis need a different collection contract.

## 007 — Keep the browser interface small

**Decision:** use browser-native HTML, CSS and JavaScript, with FastAPI serving both the API and static assets.

**Reason:** the analytical product does not need a separate frontend build system or a large UI framework. The visual language can stay specific to the project and the network path stays easy to inspect.

**Consequence:** the interface is intentionally a focused research application. More complex user accounts, saved profiles or collaborative workflows would require a new design decision.
