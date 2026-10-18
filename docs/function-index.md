# Function and class index

Start with the [four entry points](start-here.md). This page is a lookup reference, not a list of everything to learn before running the app. Source links point to definitions; their docstrings explain input, output, errors and effects.

## 1. Commands

### `cli.py`

| Definition | Purpose |
| --- | --- |
| [`environment_report`](../careergraph/cli.py#L27) | Inspect this installation without collecting data or creating a database. |
| [`main`](../careergraph/cli.py#L107) | Dispatch one explicit local operation from the project's single entry point. |

## 2. Sources

### `connectors.py`

| Definition | Purpose |
| --- | --- |
| [class `JobTechConnector`](../careergraph/connectors.py#L25) | Operational class for the advert provider. |
| [`JobTechConnector.__init__`](../careergraph/connectors.py#L34) | Configure the official advert adapter without collecting anything. |
| [`JobTechConnector.collect`](../careergraph/connectors.py#L48) | Retrieve a bounded advert batch and its source-request audit. |
| [`JobTechConnector.normalize`](../careergraph/connectors.py#L120) | Map one provider advert into the application's Offer input fields. |
| [class `EurostatConnector`](../careergraph/connectors.py#L156) | Operational class for official aggregate statistics. |
| [`EurostatConnector.__init__`](../careergraph/connectors.py#L162) | Configure the official-statistics adapter independently of adverts. |
| [`EurostatConnector.fetch_snapshot`](../careergraph/connectors.py#L176) | Retrieve the pinned quarterly official vacancy-rate series. |
| [`iso_date`](../careergraph/connectors.py#L218) | Convert a provided source timestamp to its calendar date. |
| [`normalize_jobtech`](../careergraph/connectors.py#L233) | Retain the original function shortcut for advert normalization. |
| [`fetch_jobtech`](../careergraph/connectors.py#L251) | Retain the original tuple-returning collection shortcut. |
| [`_ordered_codes`](../careergraph/connectors.py#L276) | Decode category positions from a JSON-stat dimension. |
| [`parse_eurostat`](../careergraph/connectors.py#L294) | Validate and reshape official JSON-stat cells into analytical rows. |
| [`parse_eurostat.cell`](../careergraph/connectors.py#L334) | Read one dense or sparse JSON-stat cell. |
| [`fetch_benchmark`](../careergraph/connectors.py#L396) | Retain the original official-snapshot function shortcut. |

### `http.py`

| Definition | Purpose |
| --- | --- |
| [class `SourceError`](../careergraph/http.py#L16) | A safe provider or transport failure that must not publish partial data. |
| [class `ResponseReader`](../careergraph/http.py#L20) | Internal transport protocol describing read(size). Not a runtime object the project user needs to construct. |
| [`ResponseReader.read`](../careergraph/http.py#L23) | Describe the byte reader expected from an HTTP transport. |
| [class `Opener`](../careergraph/http.py#L38) | Internal transport protocol describing timed context-managed response opening. Only transport tests replace it. |
| [`Opener.__call__`](../careergraph/http.py#L41) | Describe the injectable request-opening interface. |
| [`retry_delay`](../careergraph/http.py#L59) | Interpret a provider delay without retrying earlier than requested. |
| [`open_response`](../careergraph/http.py#L90) | Adapt urllib to the small response-reader contract. |
| [`get_json`](../careergraph/http.py#L110) | Retrieve one bounded provider JSON object with transient retries. |

## 3. Validated storage

### `pipeline.py`

| Definition | Purpose |
| --- | --- |
| [class `CollectionService`](../careergraph/pipeline.py#L29) | Operational class coordinating one advert-to-database workflow. |
| [`CollectionService.__init__`](../careergraph/pipeline.py#L35) | Select the database used by this collection service. |
| [`CollectionService.collect`](../careergraph/pipeline.py#L49) | Audit and publish one complete source/country collection. |
| [`identity_record`](../careergraph/pipeline.py#L101) | Copy the top level of an already-normalized fixture. |
| [`now`](../careergraph/pipeline.py#L116) | Create a timezone-aware collection-audit timestamp. |
| [`begin_run`](../careergraph/pipeline.py#L128) | Initialize the schema and create a running collection audit. |
| [`fail_run`](../careergraph/pipeline.py#L167) | Record a failed attempt without exposing arbitrary provider error bodies. |
| [`ingest`](../careergraph/pipeline.py#L200) | Validate, deduplicate and atomically store a complete offer sample. |
| [`collect_jobtech`](../careergraph/pipeline.py#L354) | Run the public advert workflow through its adapter and service. |
| [`save_benchmark`](../careergraph/pipeline.py#L388) | Store an already-validated official snapshot independently of adverts. |

### `models.py`

| Definition | Purpose |
| --- | --- |
| [class `Offer`](../careergraph/models.py#L10) | Validated advert model, not a source client. |
| [`Offer.valid_country`](../careergraph/models.py#L31) | Validate an advert country while constructing an Offer. |
| [`Offer.valid_role`](../careergraph/models.py#L47) | Validate an advert role family while constructing an Offer. |
| [`Offer.safe_url`](../careergraph/models.py#L65) | Validate the source-link structure while constructing an Offer. |

### `db.py`

| Definition | Purpose |
| --- | --- |
| [`default_db`](../careergraph/db.py#L8) | Choose the configured local database filename. |
| [`connect`](../careergraph/db.py#L21) | Open one SQLite transaction and always close its connection. |
| [`init_db`](../careergraph/db.py#L53) | Create the versioned tables and indexes if they are absent. |

## 4. Analysis and matching

### `analysis.py`

| Definition | Purpose |
| --- | --- |
| [`latest_runs`](../careergraph/analysis.py#L16) | Select one latest successful run per provider/workplace scope. |
| [`cohort`](../careergraph/analysis.py#L45) | Load the current filtered offers and their exact evidence. |
| [`skill_bridge`](../careergraph/analysis.py#L130) | Count the exact additional coverage from one skill. |
| [`describe`](../careergraph/analysis.py#L177) | Summarize one cohort while preserving the caller's offers and audits. |
| [`overview`](../careergraph/analysis.py#L256) | Combine cohort metrics with the most recent collection attempts. |
| [`evidence`](../careergraph/analysis.py#L307) | Page the adverts behind a selected skill result. |
| [`benchmark`](../careergraph/analysis.py#L369) | Read the latest attributed official snapshot for a country filter. |
| [`coverage`](../careergraph/analysis.py#L419) | Report the difference between configured and connected markets. |

### `text.py`

| Definition | Purpose |
| --- | --- |
| [class `PlainText`](../careergraph/text.py#L12) | Internal stateful HTML parser used only by clean_text. |
| [`PlainText.__init__`](../careergraph/text.py#L18) | Initialize the internal HTML-to-text parser. |
| [`PlainText.handle_starttag`](../careergraph/text.py#L31) | Handle an opening HTML tag during sanitization. |
| [`PlainText.handle_endtag`](../careergraph/text.py#L49) | Handle a closing HTML tag while preserving word boundaries. |
| [`PlainText.handle_data`](../careergraph/text.py#L66) | Retain visible text outside script and style elements. |
| [`clean_text`](../careergraph/text.py#L82) | Convert provider HTML into stable text for validation and evidence offsets. |
| [`folded`](../careergraph/text.py#L105) | Normalize case and accents for conservative title matching. |
| [`role_family`](../careergraph/text.py#L122) | Assign the first configured role family matching the advert title. |
| [`extract_skills`](../careergraph/text.py#L154) | Extract the first literal mention of each known skill. |

### `catalog.py`

| Definition | Purpose |
| --- | --- |
| [`read_config`](../careergraph/catalog.py#L13) | Load one bundled configuration file as a JSON object. |
| [`country_code`](../careergraph/catalog.py#L39) | Normalize a country parameter and validate its configured scope. |
| [`validate_skills`](../careergraph/catalog.py#L63) | Validate user-selected skill identifiers against the local vocabulary. |

## 5. Read-only interface

### `api.py`

| Definition | Purpose |
| --- | --- |
| [`create_app`](../careergraph/api.py#L20) | Assemble the local read-only API around one database. |
| [`create_app.invalid_value`](../careergraph/api.py#L47) | Translate an analytical parameter error to an HTTP response. |
| [`create_app.response_headers`](../careergraph/api.py#L63) | Apply local browser response policy to each request. |
| [`create_app.home`](../careergraph/api.py#L88) | Serve the packaged English interface. |
| [`create_app.health`](../careergraph/api.py#L100) | Report that the local API process can answer a request. |
| [`create_app.catalog`](../careergraph/api.py#L112) | Expose the versioned UI configuration. |
| [`create_app.get_overview`](../careergraph/api.py#L130) | Serve GET /api/overview using the shared analytical calculation. |
| [`create_app.get_evidence`](../careergraph/api.py#L168) | Serve the bounded advert-evidence drill-down. |
| [`create_app.get_benchmark`](../careergraph/api.py#L212) | Serve official context separately from observed skill demand. |
| [`create_app.get_coverage`](../careergraph/api.py#L230) | Serve the country coverage ledger. |

## Utilities and static contracts

### `demo.py`

| Definition | Purpose |
| --- | --- |
| [`demo_records`](../careergraph/demo.py#L47) | Build the deterministic fictional software dataset. |
| [`seed_demo`](../careergraph/demo.py#L93) | Store the authored demo using its fixed fixture calendar date. |

### `evaluation.py`

| Definition | Purpose |
| --- | --- |
| [`evaluate`](../careergraph/evaluation.py#L10) | Compare skill mentions with an authored regression-case file. |

### `contracts.py`

| Definition | Purpose |
| --- | --- |
| [class `AliasSpec`](../careergraph/contracts.py#L16) | Dictionary schema for a label and its literal aliases. No runtime object construction is required. |
| [class `SkillSpec`](../careergraph/contracts.py#L23) | Dictionary schema for one stable local skill ID, label and aliases. This is not an ESCO ID mapping. |
| [class `Vocabulary`](../careergraph/contracts.py#L29) | Dictionary schema for the bundled skill version, explanatory description and skill list. |
| [class `CohortFilters`](../careergraph/contracts.py#L37) | Dictionary schema listing optional country/role/date/origin filters. It is a type description, not a filter engine. |
| [class `SkillMention`](../careergraph/contracts.py#L46) | Extractor-output dictionary schema. start/end are Python string offsets into sanitized text; the end is exclusive. |
| [class `StoredSkillMention`](../careergraph/contracts.py#L56) | Stored/API evidence dictionary schema. Keeps start_offset/end_offset field names compatible with the SQL contract. |
| [class `BenchmarkRow`](../careergraph/contracts.py#L66) | Dictionary schema for one official country/quarter observation; a missing rate or flag remains None. |
| [class `BenchmarkSnapshot`](../careergraph/contracts.py#L75) | Dictionary schema for one attributed official-statistics retrieval, its metadata, hash and country/quarter cells. |
| [class `CollectionBatch`](../careergraph/contracts.py#L86) | Data container, not an active service. |
| [class `AdvertConnector`](../careergraph/contracts.py#L96) | Static interface contract for an advert adapter. |
| [`AdvertConnector.collect`](../careergraph/contracts.py#L105) | Specify how an advert adapter retrieves one bounded batch. |
| [`AdvertConnector.normalize`](../careergraph/contracts.py#L125) | Specify the mapping from a provider hit to Offer input fields. |

The container-only entry point is [`scripts/container-start.py`](../scripts/container-start.py). It may initialize the complete demo on a fresh volume and is not part of the small checks.
