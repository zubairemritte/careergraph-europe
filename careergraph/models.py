from datetime import date
from typing import ClassVar, Literal
from urllib.parse import SplitResult, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from careergraph.catalog import ROLES, country_code


class Offer(BaseModel):
    """Validated normalized advert fields; unknown fields and unsafe URLs are rejected."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: str = Field(min_length=1, max_length=200)
    country: str
    title: str = Field(min_length=2, max_length=500)
    company: str = Field(min_length=1, max_length=300)
    location: str = Field(max_length=300)
    description: str = Field(min_length=30, max_length=100000)
    published_at: date
    expires_at: date | None = None
    source_url: str = Field(max_length=2000)
    role: str
    kind: Literal["demo", "live"]

    @field_validator("country")
    @classmethod
    def valid_country(cls, value: str) -> str:
        """Validate the offer workplace country against the supported filter catalog."""
        return country_code(value)

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        """Reject role IDs that are absent from the configured classifier vocabulary."""
        if value not in ROLES:
            raise ValueError("Unknown role family")
        return value

    @field_validator("source_url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        """Require a public HTTPS source link without embedded account credentials."""
        parsed: SplitResult = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("A public HTTPS source URL is required")
        return value
