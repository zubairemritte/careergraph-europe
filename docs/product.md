# Product brief

## Problem

Job titles are inconsistent, descriptions mix essential and optional skills, and the coverage of online job sources is uneven. A chart can look convincing while silently counting duplicate adverts, treating missing data as zero or comparing incomparable samples.

CareerGraph Europe lets a user inspect a defined offer sample and relate its skill mentions to a chosen skill set. The product is designed around three questions:

1. What is mentioned repeatedly in the selected offers?
2. Which single skill addition would complete more of their detected skill sets?
3. Can I trace the answer back to the source and understand the sample's limits?

## Users and decisions

| User | Decision supported | Evidence required |
| --- | --- | --- |
| A data professional | Which skill should I investigate next? | Additional covered offers, underlying texts, role and country filters |
| A career adviser | How should I explain the observed skill landscape? | Explicit denominator, recognisable labels, source/date context |
| A labour-market analyst | Is this sample useful enough to analyse? | Source scope, failures, duplicates, rejected records, collection caps |

The application supports the user's research. It neither evaluates job applicants nor makes employment decisions.

## First release journey

1. Choose an illustrative or collected offer dataset.
2. Filter by country, title-based role family and publication date.
3. Inspect skill frequencies and the size of the sample.
4. Select skills you want to compare; the default is Python and SQL, not a stored personal profile.
5. Inspect the additional offers associated with one skill.
6. Read the extracted snippets and open the original advert when available.
7. Check official economic context and the coverage ledger.

The interface is in English. Country configuration includes major European economies and neighbouring markets; list order is alphabetical and has no ranking meaning.

## Distinctive product choices

**Evidence first.** Every detected skill is linked to an exact span in the sanitized description. A recommendation cannot hide behind an unexplained score.

**Data quality is visible.** Counts of received, accepted, duplicated and rejected records are inspectable. A source or country that has not been collected remains visibly unavailable.

**An actionable, bounded measure.** A frequent skill may not be useful as the *next* addition for a particular skill set. Marginal coverage connects observed mentions with the user's current selection without claiming causality.

**Separate analytical levels.** Job adverts describe an observed online sample. Eurostat describes a published economic statistic. The application shows both without merging their denominators.

## Included and excluded

| Implemented | Not implemented in 0.1 |
| --- | --- |
| Country-variable data model and 16-country demo | Verified live offer coverage in all 16 countries |
| JobTech connector and Eurostat connector | EURES partner access or licensed Adzuna analytics |
| Dictionary-based skill mentions and limited role aliases | Evaluated semantic/LLM extraction or ESCO mapping |
| Explicit skill selection | CV parsing, storage or automated CV scoring |
| Dated successful snapshots | Long-running change-data capture or vacancy survival analysis |
| Co-occurrence and one-skill coverage | Causal salary returns, salary predictions or hiring probabilities |
| Local application, tests, CI file, Docker recipe | Hosted production service, SLA or cloud infrastructure |

## Acceptance criteria

- A fresh checkout can produce a meaningful offline demonstration.
- Demo and collected offers cannot enter the same cohort.
- Unsupported country/source combinations fail before making network requests.
- Re-running collection does not double-count current offers.
- A failed refresh does not replace a valid snapshot.
- Displayed skill gains reconcile with their evidence drill-down.
- Missing statistics stay missing, and source flags remain available.
- Documentation explains how to reproduce the reported measures.

The release report identifies which checks have been executed and which deployment paths are only provided as configuration.
