# Source register and country coverage

Reviewed on **7 October 2026**. Access, coverage and reuse terms can change. The register records this release's decisions, not a permanent certification of a provider.

## Active sources

| Source | Owner / authority | Role in CareerGraph | Access tested | Reuse / attribution |
| --- | --- | --- | --- | --- |
| [JobSearch / JobTech](https://data.arbetsformedlingen.se/dataservice/jobsearch/) | Arbetsförmedlingen, the Swedish public employment service | Individual online advertisements | Public JSON API, no key; successful bounded collection | Provider lists CC0. Source URL and collection timestamp retained. |
| [Eurostat `jvs_q_r21`](https://ec.europa.eu/eurostat/databrowser/view/jvs_q_r21/default/table) | Eurostat, European Commission | Broad economic vacancy context | Public Statistics API, JSON-stat 2.0; successful retrieval | Reuse with attribution, subject to published exceptions. The derived export names the source and transformation. |

### JobTech: what is actually covered

Endpoint: `https://jobsearch.api.jobtechdev.se/search`.

The initial run uses four English keyword queries, bounded to two pages of 100 records each. Results are neither a census nor an English-language-only corpus. Source matching can be broader than the query title. The `analytics engineer` query hit the configured page cap in the release smoke run; that truncation is recorded.

The feed can contain jobs located outside Sweden. The adapter admits only records with the verified workplace-country concept `i46j_HmG_v64`. It does not mistake the provider's numeric country code `199` for ISO alpha-2. Foreign or unknown workplace countries are rejected with a recorded reason.

Only normalized analytical fields are stored. Structured employer contact fields and application-contact fields are not copied. Live advertisement bodies, local databases and contact information are not committed to this repository. The [provider's dataset page](https://data.arbetsformedlingen.se/dataset/job-ads/) describes the available streams and historical services; this release uses bounded search snapshots only.

### Eurostat: the exact series matters

Endpoint: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/jvs_q_r21`.

The connector requests quarterly, seasonally adjusted job vacancy rates for NACE Rev. 2.1 B–T and total enterprise sizes. It retains the last eight available quarters, source update time, retrieval time, status flags, request URL and a SHA-256 digest of canonicalized response JSON.

The export is a selection and reshaping of official statistics. It does not calculate a new vacancy rate. Missing data is null. The source's national coverage differences still apply, and no occupation-specific interpretation is justified.

References:

- [Statistics API documentation](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-getting-started)
- [Job vacancy statistics and coverage notes](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Job_vacancy_statistics)
- [Copyright and reuse notice](https://ec.europa.eu/eurostat/en/help/copyright-notice)

**Attribution:** Source: Eurostat, `jvs_q_r21`, accessed 7 October 2026 for the bundled snapshot. Selected and reshaped by CareerGraph Europe. Eurostat is not responsible for the conclusions or presentation. Do not imply endorsement. Commercial reuse must also respect the notice's third-party and geographical exceptions.

## Evaluated, not activated

| Candidate | Intended contribution | Decision for 0.1 |
| --- | --- | --- |
| [ESCO](https://esco.ec.europa.eu/en/use-esco/use-esco-services-api/esco-web-service-api) | Multilingual occupation/skill reference concepts | Relevant official taxonomy, but not an offer feed. The test request did not yield a usable response. No ESCO integration or mapping is claimed; current skill IDs are local. A later integration must pin its version and validate concept URIs. |
| [EURES](https://europa.eu/eures/portal/jv-se/home?lang=en) | Potential cross-border offer network | Its published job-search terms reserve extraction through the API to recognised partners and disallow extraction/republication through scraping. Not connected; a reverse-engineered endpoint is not a substitute for authorised access. |
| [Adzuna API](https://developer.adzuna.com/overview) | Potential multi-country commercial offer coverage | Requires an app ID/key. Its [API terms](https://developer.adzuna.com/docs/terms_of_service) distinguish permitted uses and impose conditions on ongoing aggregated use. No data collected; a suitable permission/licence must be established for the intended public analytics. |

No connector scrapes LinkedIn, Indeed or EURES. A site being publicly viewable does not establish that its data can be extracted and republished for this product.

## Geographic contract

The configuration currently includes **AT, BE, DK, FI, FR, DE, IE, IT, LU, NL, PL, PT, ES, SE, CH and GB**. Countries are model parameters, not part of an employer-targeting tagline.

There are three different questions for each country:

1. Is the country recognised by the product's configuration?
2. Is a verified offer connector connected and has it collected a sample?
3. Does the selected official statistical series have an observed value for the displayed quarter?

The `/api/coverage` endpoint answers these separately. `not_connected`, `connector_ready`, `collected` and statistical `unavailable` are deliberate states. A successful zero-result search is an **empty sample**; it is not the same as an uncollected country.

## Adding an offer source

Before enabling a new connector, record its owner, official documentation, supported countries, authentication, rate limits, pagination, attribution, retention and permitted analytical use. Then implement normalization to the existing `Offer` contract and add contract fixtures.

Demonstrate a real successful run, verify country semantics and exact source links, inspect unmatched roles and extracted evidence, and update the coverage ledger. Do not change the country label on another provider's records to create apparent coverage.

Credential-requiring integrations should use runtime secrets and redact logs. They do not belong in public source files, examples or URLs committed to Git.
