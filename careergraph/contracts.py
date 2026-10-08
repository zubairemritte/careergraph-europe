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
    """An English label and its literal matching aliases."""

    label: str
    aliases: list[str]


class SkillSpec(AliasSpec):
    """A stable local skill identifier; it is not an ESCO identifier."""

    id: str


class Vocabulary(TypedDict):
    """The versioned skill configuration shipped with the package."""

    version: str
    description: str
    skills: list[SkillSpec]


class CohortFilters(TypedDict, total=False):
    """Optional sample filters shared by the CLI and read-only HTTP endpoints."""

    mode: str
    country: str
    role: str
    since: str | None


class SkillMention(TypedDict):
    """One exact match into a sanitized advert description."""

    skill: str
    start: int
    end: int
    matched_text: str
    excerpt: str


class StoredSkillMention(TypedDict):
    """The persisted/API evidence contract; SQL names remain stable across releases."""

    skill: str
    start_offset: int
    end_offset: int
    matched_text: str
    excerpt: str


class BenchmarkRow(TypedDict):
    """One official country/quarter observation, including missingness."""

    country: str
    quarter: str
    vacancy_rate: float | None
    status_flag: str | None


class BenchmarkSnapshot(TypedDict):
    """A dated, attributable aggregate snapshot kept separate from adverts."""

    retrieved_at: str
    request_url: str
    payload_sha256: str
    metadata: JsonObject
    rows: list[BenchmarkRow]


@dataclass(frozen=True, slots=True)
class CollectionBatch:
    """Provider observations and the request audit for one bounded collection."""

    records: list[JsonObject]
    metadata: JsonObject


class AdvertConnector(Protocol):
    """The behaviour a new advert provider must implement before activation."""

    source_id: str
    supported_countries: frozenset[str]

    def collect(self, country: str, queries: list[str], pages: int = 2) -> CollectionBatch:
        """Retrieve a bounded batch; reject unsupported countries before any request."""
        ...

    def normalize(self, raw: JsonObject) -> JsonObject:
        """Map a provider record to Offer fields without inventing workplace coverage."""
        ...
