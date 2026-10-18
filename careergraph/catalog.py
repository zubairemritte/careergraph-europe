"""Versioned, auditable configuration; country support is separate from source coverage."""

import hashlib
import json
from pathlib import Path
from typing import cast

from careergraph.contracts import AliasSpec, JsonObject, SkillSpec, Vocabulary

CONFIG: Path = Path(__file__).parent / "config"


def read_config(name: str) -> JsonObject:
    """Load one bundled configuration file as a JSON object.

    Args:
        name: Filename relative to careergraph/config, for example skills.json.

    Returns:
        The decoded object. Callers assign the appropriate catalog field contract.

    Raises:
        OSError: The bundled file cannot be read.
        json.JSONDecodeError: The file is not valid JSON.

    Side effects:
        Reads a UTF-8 package file; never requests a source or writes data.
    """
    return cast(JsonObject, json.loads((CONFIG / name).read_text(encoding="utf-8")))


COUNTRIES: dict[str, str] = cast(dict[str, str], read_config("countries.json"))
ROLES: dict[str, AliasSpec] = cast(dict[str, AliasSpec], read_config("roles.json"))
VOCABULARY: Vocabulary = cast(Vocabulary, read_config("skills.json"))
SKILLS: dict[str, SkillSpec] = {item["id"]: item for item in VOCABULARY["skills"]}
CATALOG_HASH: str = hashlib.sha256((CONFIG / "skills.json").read_bytes()).hexdigest()


def country_code(value: str, *, allow_all: bool = False) -> str:
    """Normalize a country parameter and validate its configured scope.

    Args:
        value: ISO alpha-2 code; surrounding spaces and lowercase are accepted.
        allow_all: Whether the analytical ALL sentinel is also accepted.

    Returns:
        An uppercase configured country code, or ALL when explicitly allowed.

    Raises:
        ValueError: The value is not in the country catalog or ALL is not allowed.

    Example:
        country_code(" de ") returns "DE"; "UK" is rejected because the ISO code is GB.
    """
    code: str = value.strip().upper()
    if code not in COUNTRIES and (not (allow_all and code == "ALL")):
        raise ValueError(
            f"Unsupported country: {code}. Use an ISO alpha-2 code in the country catalog."
        )
    return code


def validate_skills(values: list[str]) -> set[str]:
    """Validate user-selected skill identifiers against the local vocabulary.

    Args:
        values: Local IDs such as python and sql, not display labels or arbitrary aliases.

    Returns:
        Normalized distinct IDs. Empty strings are discarded.

    Raises:
        ValueError: At least one nonempty ID is absent from the vocabulary.

    Example:
        validate_skills([" SQL ", "sql"]) returns {"sql"}.
    """
    result: set[str] = {value.strip().lower() for value in values if value.strip()}
    unknown: set[str] = result - SKILLS.keys()
    if unknown:
        raise ValueError("Unknown skill IDs: " + ", ".join(sorted(unknown)))
    return result
