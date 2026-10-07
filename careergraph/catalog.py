"""Versioned, auditable configuration; country support is separate from source coverage."""

import hashlib
import json
from pathlib import Path

CONFIG = Path(__file__).parent / "config"


def read_config(name: str) -> dict:
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


COUNTRIES = read_config("countries.json")
ROLES = read_config("roles.json")
VOCABULARY = read_config("skills.json")
SKILLS = {item["id"]: item for item in VOCABULARY["skills"]}
CATALOG_HASH = hashlib.sha256((CONFIG / "skills.json").read_bytes()).hexdigest()


def country_code(value: str, *, allow_all: bool = False) -> str:
    code = value.strip().upper()
    if code not in COUNTRIES and not (allow_all and code == "ALL"):
        raise ValueError(
            f"Unsupported country: {code}. Use an ISO alpha-2 code in the country catalog."
        )
    return code


def validate_skills(values: list[str]) -> set[str]:
    result = {value.strip().lower() for value in values if value.strip()}
    unknown = result - SKILLS.keys()
    if unknown:
        raise ValueError("Unknown skill IDs: " + ", ".join(sorted(unknown)))
    return result
