"""Deterministic mention extraction with exact evidence offsets into sanitized text."""

import html
import re
import unicodedata
from html.parser import HTMLParser

from careergraph.catalog import ROLES, SKILLS


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        elif tag in {"p", "br", "li", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        elif tag in {"p", "li", "div"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def clean_text(value: str) -> str:
    parser = PlainText()
    parser.feed(value)
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)", "[phone removed]", text)
    return re.sub(r"\s+", " ", text).strip()


def folded(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )


def role_family(title: str) -> str:
    title = folded(title)
    for role, spec in ROLES.items():
        if any(
            re.search(r"(?<!\w)" + re.escape(folded(a)) + r"(?!\w)", title) for a in spec["aliases"]
        ):
            return role
    return "other"


PATTERNS = {
    key: re.compile(
        r"(?<!\w)(?:"
        + "|".join(re.escape(a) for a in sorted(item["aliases"], key=len, reverse=True))
        + r")(?!\w)",
        re.IGNORECASE,
    )
    for key, item in SKILLS.items()
}


def extract_skills(text: str) -> list[dict]:
    """Keep one evidence span per skill; optional/negated mentions still count as mentions."""
    result = []
    for skill, pattern in PATTERNS.items():
        match = pattern.search(text)
        if match:
            result.append(
                {
                    "skill": skill,
                    "start": match.start(),
                    "end": match.end(),
                    "matched_text": match.group(),
                    "excerpt": text[max(0, match.start() - 65) : min(len(text), match.end() + 90)],
                }
            )
    return result
