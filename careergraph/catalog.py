"""Versioned, auditable configuration; country support is separate from source coverage."""

import hashlib
import json
from pathlib import Path
from typing import cast

from careergraph.contracts import AliasSpec, JsonObject, SkillSpec, Vocabulary

CONFIG: Path = Path(__file__).parent / "config"


def read_config(name: str) -> JsonObject:
    """Read a bundled JSON configuration; stable catalog fields are typed at the call site."""
    return cast(JsonObject, json.loads((CONFIG / name).read_text(encoding="utf-8")))


COUNTRIES: dict[str, str] = cast(dict[str, str], read_config("countries.json"))
ROLES: dict[str, AliasSpec] = cast(dict[str, AliasSpec], read_config("roles.json"))
VOCABULARY: Vocabulary = cast(Vocabulary, read_config("skills.json"))
SKILLS: dict[str, SkillSpec] = {item["id"]: item for item in VOCABULARY["skills"]}
CATALOG_HASH: str = hashlib.sha256((CONFIG / "skills.json").read_bytes()).hexdigest()


def country_code(value: str, *, allow_all: bool = False) -> str:
    """Normalize an ISO alpha-2 parameter and reject countries outside the configured catalog."""
    code: str = value.strip().upper()
    if code not in COUNTRIES and (not (allow_all and code == "ALL")):
        raise ValueError(
            f"Unsupported country: {code}. Use an ISO alpha-2 code in the country catalog."
        )
    return code


def validate_skills(values: list[str]) -> set[str]:
    """Return normalized known skill IDs; reject unknown IDs rather than invent aliases."""
    result: set[str] = {value.strip().lower() for value in values if value.strip()}
    unknown: set[str] = result - SKILLS.keys()
    if unknown:
        raise ValueError("Unknown skill IDs: " + ", ".join(sorted(unknown)))
    return result
