# Analytical methodology

## 1. Define the observational unit

The unit is a retained **advertisement in a successful collection snapshot**. It is not an individual vacancy, a hire, an employer, or a representative person in the labour market. An advert can cover several positions, and one position can appear in several adverts.

The application selects the latest successful run for each source/workplace-country pair within the selected mode. It then applies country, role and publication-date filters. The current release has one live offer source.

**Let N be the number of retained adverts in this filtered cohort.** Every offer-based percentage is conditional on that cohort, its queries, the source's matching behaviour and any page cap.

## 2. Skill detection

The first release recognises 24 skills using a curated, versioned dictionary. Matching is case-insensitive, uses word boundaries and checks aliases such as `PowerBI` and `Power BI`. Each skill is counted at most once per advert.

Evidence offsets point to the sanitized **description**, not the original HTML and not a concatenation of title and description. The title is used only for role classification. Sanitization removes markup, scripts, email patterns and common phone patterns. It is data minimization, not a guarantee that every personal reference has been removed.

Matches are **mentions**. The baseline does not reliably distinguish:

- required from desirable skills;
- a candidate requirement from the employer's technology stack;
- negation, such as “SQL is not required”;
- an ambiguous product name from an ordinary word.

For example, the word “Tableau” can be ambiguous in French, “Snowflake” can have non-product meanings, and a bare `R` is intentionally not matched. Explicit forms such as `R programming`, `RStudio` and `langage R` are recognised. These are known precision/recall trade-offs, not solved NLP problems.

The 32 authored regression cases protect known behaviour. Their metrics **do not estimate real-world extraction accuracy**. General accuracy requires a separate, independently reviewed corpus of real descriptions stratified by source, role and language. ESCO mappings are not implemented; local skill IDs must not be presented as ESCO concept URIs.

## 3. Skill frequency

For skill s, count each advert once if s occurs in its detected skill set S:

```text
count(s) = number of retained adverts containing s
share(s) = count(s) / N
```

Adverts without recognised skills stay in the denominator. This keeps low extraction coverage visible instead of inflating apparent skill prevalence. The shares need not sum to 100%, because adverts mention several skills.

The UI shows counts and denominators. It flags samples smaller than 30 as exploratory. That threshold is a product heuristic, not a statistical guarantee. No confidence interval can repair the selection bias of a non-probability online sample, so the interface does not present one as national uncertainty.

## 4. One-skill coverage

Let K be the user's explicitly selected skills. Let E be adverts with at least one recognised skill. Adverts with no detected skills are excluded from this calculation; otherwise an empty set would make them look automatically covered.

An advert is covered when all its detected mentions belong to K:

```text
covered(K) = number of j in E for which S_j is a subset of K
gain(s | K) = covered(K union {s}) - covered(K), for s not in K
```

An equivalent implementation counts adverts whose only missing detected skill is s. This equivalence makes the result straightforward to test and the drill-down exact.

### A worked example

Current selection K = {Python, SQL}.

| Advert | Detected skills | Missing skills |
| --- | --- | --- |
| A | Python, SQL | None |
| B | Python, SQL, dbt | dbt |
| C | SQL, dbt | dbt |
| D | Python, Docker, AWS | Docker, AWS |
| E | None | Unknown; excluded |

There are four eligible adverts. The baseline is 1/4. Adding dbt covers two more: the new level is 3/4. Adding Docker alone covers none, because D still needs AWS.

The gain is **2 adverts, or 50 percentage points of this eligible sample**. It is not a 50% increase in hiring probability. Results for different additions are separate one-step scenarios; they are not a multi-step curriculum optimiser and should not be added without recalculating.

### Interpretation limits

Skill coverage does not establish mastery, experience, language proficiency, education, work permission, location fit or interest in the role. It also misses skills outside the vocabulary. Optional and negated mentions can distort it. The product therefore links to the underlying advert and does not call the result “employability”.

## 5. Skill relationships

Skills are graph nodes. An edge represents co-occurrence in the same retained advert.

```text
support(A, B) = number of adverts mentioning both
Jaccard(A, B) = support(A, B) / (count(A) + count(B) - support(A, B))
```

The UI requires at least three shared adverts and orders edges by support, then Jaccard. Both measures are descriptive. A high overlap does not show that learning one skill causes another skill, a salary increase or a hire. The displayed list is a readable representation of the weighted skill graph.

## 6. Duplicates and historical runs

Within a run, the collector keeps the first accepted occurrence of a source ID. It also removes exact duplicates under different IDs using a fingerprint of country, company, location, title, publication date and sanitized description, after case-folding.

This is deliberately conservative. It does not claim to solve near-duplicate reposts, multi-agency advertising or all cross-source duplicates. Including publication date avoids silently merging distinct reposting dates. No cross-source merging is needed for the single live connector in this release.

Repeated collections create new snapshots. Analysis uses the latest successful one and therefore does not sum historical observations. Absence from a bounded keyword search does not prove a vacancy was closed. History is a history of **observations**, not a complete vacancy lifecycle.

## 7. Official economic context

Eurostat's job vacancy rate relates vacant posts to occupied plus vacant posts in its defined economic scope. The connector pins:

| Dimension | Value |
| --- | --- |
| Dataset | `jvs_q_r21` |
| Frequency | `Q` |
| NACE Rev. 2.1 | `B-T` |
| Enterprise size | `TOTAL` |
| Seasonal adjustment | `SA` |
| Indicator | `JVR` |
| Period window | Last eight available quarters at retrieval |

JSON-stat dimension order is decoded from metadata. Missing cells remain null; status flags are preserved. The current-quarter view uses one common quarter, not each country's latest nonmissing value.

The broad sector aggregate is **not a measure of data-professional vacancies**. National coverage exceptions remain relevant even when the series code is shared. The [official methodology](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Job_vacancy_statistics) documents differences, including coverage limitations for public institutions and for Denmark.

The new NACE Rev. 2.1 series is used explicitly. The application does not silently concatenate it with the older `jvs_q_nace2` series or assume that sector letters retain the same meaning.

## 8. What comparisons are defensible?

Compare descriptions within a stated source/role/query/period cohort. Before comparing countries or time periods, inspect source coverage, search terms, source mix, vocabulary version and publication windows. A country with no connected offer feed has **unobserved demand**, not zero demand.

This release deliberately does not produce a composite “best country for your career” score: there is no defensible common scale for the available components yet.
