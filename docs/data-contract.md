# Data contract

## Offer

| Field | Type / rule | Meaning |
| --- | --- | --- |
| `source_id` | Nonempty string, ≤200 characters | Provider-local identifier |
| `country` | Configured ISO alpha-2 | Workplace country, never nationality or audience target |
| `title` | 2–500 characters | Sanitized source title |
| `company` | 1–300 characters | Sanitized employer name; explicit fallback if absent |
| `location` | String, ≤300 characters | City/municipality if available; empty stays empty |
| `description` | 30–100,000 characters | Sanitized description used for extraction |
| `published_at` | Date | Source publication date; must not be in the future relative to the run |
| `expires_at` | Nullable date | Advertised deadline if present; already expired rows are rejected |
| `source_url` | HTTPS URL without credentials | Link to original advert; demo uses reserved `example.invalid` URLs |
| `role` | Configured enum | Rule-derived title family, including `other` |
| `kind` | `demo` or `live` | Must match the run's data mode |

The record stores dates rather than timestamps for publication/deadline filtering. Source-local time precision is intentionally reduced to the date. Collection timestamps are UTC.

## Relational tables

| Table | Key | Purpose |
| --- | --- | --- |
| `runs` | `run_id` | Source, mode, workplace-country scope, query configuration, start/end times, status, vocabulary hash and report |
| `offers` | `(run_id, offer_id)` | Immutable normalized adverts for a successful observation run |
| `skill_mentions` | `(run_id, offer_id, skill)` | One evidence span per detected skill and advert |
| `benchmark_snapshots` | `snapshot_id` | Source request, retrieval/update times, dimensions and payload hash |
| `benchmarks` | `(snapshot_id, country, quarter)` | Official rate or null, plus status flag |

`offer_id` is a deterministic hash of the source namespace and source ID. A distinct source cannot accidentally reuse another source's identifier. The same advert ID can appear in multiple historical runs.

## Quality accounting

For each successful run:

```text
input_records = accepted_offers + duplicates_removed + rejected_records
```

Duplicates are counted after normalization and validation. Rejection reports retain a bounded set of source IDs and reasons, not raw payloads. Common reasons are `invalid_record`, `outside_verified_country`, `removed_offer`, `future_publication_date`, `expired_offer` and a mode/country mismatch.

These are **collection-level** counts. They must not be relabelled as counts after the UI's country, role or date filters. The UI and API state that scope explicitly.

## Missingness

- Missing salary is not zero. Salary is outside the release contract and is not inferred.
- Missing recognized skills does not mean the advert requires no skills.
- An unavailable official statistic remains null.
- A disconnected source is not a successful search returning no results.
- A title without a recognized alias goes to `other`, never to a guessed data role.

## Evidence semantics

`start_offset` and `end_offset` use Python string indices into the sanitized description, with an exclusive end offset. `description[start_offset:end_offset]` must equal `matched_text`. `excerpt` adds bounded surrounding context for review. The API exposes snippets, not the full description.

The vocabulary file's SHA-256 digest is recorded in each run. Existing snapshots retain their stored matches. Changing the vocabulary does not silently relabel old observations; recollect or reprocess deliberately and record a new run.

## Official-statistics contract

The parser checks the entire expected dimension set and the pinned series values. It decodes arbitrary dimension order and both sparse-object and dense-array JSON-stat values. It accepts numeric vacancy rates from 0 to 100, retains null cells and preserves status flags.

`GB` is the product's ISO code. The current selected Eurostat series does not supply a usable current UK value under that code; the release does not substitute another country's result or silently import a different historical UK series.

## Raw data policy

No raw responses, application contacts or live database are tracked by Git. The application retains only normalized local observations, evidence excerpts, source identifiers and the collection record. Public examples contain authored fixtures and attributed aggregate official statistics. Publishing application code does not change source-data terms.
