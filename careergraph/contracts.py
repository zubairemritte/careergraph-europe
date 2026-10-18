"""Shared contracts for source boundaries and validated analytical evidence.

JsonObject is deliberately limited to heterogeneous provider/SQL/response objects.
Offer validates advert fields at runtime; the structures below type stable fields.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict

type JsonObject = dict[str, Any]
type JsonFetcher = Callable[[str], JsonObject]
type Normalizer = Callable[[JsonObject], JsonObject]


class AliasSpec(TypedDict):
    """Dictionary schema for a label and its literal aliases. No runtime object construction is required."""

    label: str
    aliases: list[str]


class SkillSpec(AliasSpec):
    """Dictionary schema for one stable local skill ID, label and aliases. This is not an ESCO ID mapping."""

    id: str


class Vocabulary(TypedDict):
    """Dictionary schema for the bundled skill version, explanatory description and skill list."""

    version: str
    description: str
    skills: list[SkillSpec]


class CohortFilters(TypedDict, total=False):
    """Dictionary schema listing optional country/role/date/origin filters. It is a type description, not a filter engine."""

    mode: str
    country: str
    role: str
    since: str | None


class SkillMention(TypedDict):
    """Extractor-output dictionary schema. start/end are Python string offsets into sanitized text; the end is exclusive."""

    skill: str
    start: int
    end: int
    matched_text: str
    excerpt: str


class StoredSkillMention(TypedDict):
    """Stored/API evidence dictionary schema. Keeps start_offset/end_offset field names compatible with the SQL contract."""

    skill: str
    start_offset: int
    end_offset: int
    matched_text: str
    excerpt: str


class BenchmarkRow(TypedDict):
    """Dictionary schema for one official country/quarter observation; a missing rate or flag remains None."""

    country: str
    quarter: str
    vacancy_rate: float | None
    status_flag: str | None


class BenchmarkSnapshot(TypedDict):
    """Dictionary schema for one attributed official-statistics retrieval, its metadata, hash and country/quarter cells."""

    retrieved_at: str
    request_url: str
    payload_sha256: str
    metadata: JsonObject
    rows: list[BenchmarkRow]


@dataclass(frozen=True, slots=True)
class CollectionBatch:
    """Data container, not an active service.

    Carries the records and request audit produced by an advert adapter. Frozen fields prevent replacement; the contained record list is not deeply immutable.
    """

    records: list[JsonObject]
    metadata: JsonObject


class AdvertConnector(Protocol):
    """Static interface contract for an advert adapter.

    Not a class to instantiate. A provider must expose source_id, supported_countries, collect and normalize; CollectionService uses that shared behaviour.
    """

    source_id: str
    supported_countries: frozenset[str]

    def collect(self, country: str, queries: list[str], pages: int = 2) -> CollectionBatch:
        """Specify how an advert adapter retrieves one bounded batch.

        Args:
            country: Workplace code explicitly declared in the adapter's supported_countries.
            queries: Search terms whose provider-specific bounds the adapter must validate.
            pages: Maximum requested pages per query; the adapter enforces its permitted budget.

        Returns:
            CollectionBatch with provider records and request metadata.

        Raises:
            ValueError: An implementation must reject unsupported country/search settings.
            SourceError: A concrete provider cannot supply a valid response.

        Side effects:
            Interface declaration only. Implementations perform retrieval; storage belongs to CollectionService.
        """
        ...

    def normalize(self, raw: JsonObject) -> JsonObject:
        """Specify the mapping from a provider hit to Offer input fields.

        Args:
            raw: One untrusted provider observation.

        Returns:
            A new Offer-shaped dictionary; runtime validation remains mandatory.

        Raises:
            ValueError: An implementation rejects out-of-scope or invalid provider fields.

        Side effects:
            Interface declaration only. Normalization should not fetch, store or change the caller's observation.
        """
        ...
