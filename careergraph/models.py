from datetime import date
from typing import ClassVar, Literal
from urllib.parse import SplitResult, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from careergraph.catalog import ROLES, country_code


class Offer(BaseModel):
    """Validated advert model, not a source client.

    Use Offer.model_validate only after provider fields have been normalized. Pydantic checks actual values; annotations alone do not validate external JSON.
    """

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
        """Validate an advert country while constructing an Offer.

        Args:
            value: Normalized workplace country received from a source adapter.

        Returns:
            The configured uppercase country code.

        Raises:
            ValueError: The country is unsupported; Pydantic reports a field validation error.
        """
        return country_code(value)

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        """Validate an advert role family while constructing an Offer.

        Args:
            value: A configured role ID, including the explicit other fallback.

        Returns:
            The unchanged valid role ID.

        Raises:
            ValueError: The role ID does not exist in config/roles.json.
        """
        if value not in ROLES:
            raise ValueError("Unknown role family")
        return value

    @field_validator("source_url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        """Validate the source-link structure while constructing an Offer.

        Args:
            value: Original advert link supplied by the source adapter.

        Returns:
            The unchanged HTTPS URL with a hostname and no embedded credentials.

        Raises:
            ValueError: The URL has no HTTPS scheme/hostname or contains credentials.

        Side effects:
            Parses the URL only. Does not contact it or verify that the advert still exists.
        """
        parsed: SplitResult = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("A public HTTPS source URL is required")
        return value
