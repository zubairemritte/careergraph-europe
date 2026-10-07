from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from careergraph.catalog import ROLES, country_code


class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str = Field(min_length=1, max_length=200)
    country: str
    title: str = Field(min_length=2, max_length=500)
    company: str = Field(min_length=1, max_length=300)
    location: str = Field(max_length=300)
    description: str = Field(min_length=30, max_length=100_000)
    published_at: date
    expires_at: date | None = None
    source_url: str = Field(max_length=2000)
    role: str
    kind: Literal["demo", "live"]

    @field_validator("country")
    @classmethod
    def valid_country(cls, value):
        return country_code(value)

    @field_validator("role")
    @classmethod
    def valid_role(cls, value):
        if value not in ROLES:
            raise ValueError("Unknown role family")
        return value

    @field_validator("source_url")
    @classmethod
    def safe_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("A public HTTPS source URL is required")
        return value
