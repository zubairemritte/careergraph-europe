"""Deterministic mention extraction with exact evidence offsets into sanitized text."""

import html
import re
import unicodedata
from html.parser import HTMLParser

from careergraph.catalog import ROLES, SKILLS
from careergraph.contracts import SkillMention


class PlainText(HTMLParser):
    def __init__(self) -> None:
        """Initialize parser state without retaining scripts or style contents."""
        super().__init__()
        self.parts: list[str] = []
        self.skip: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Suppress executable/style content and keep word boundaries between block elements."""
        if tag in {"script", "style"}:
            self.skip += 1
        elif tag in {"p", "br", "li", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        """Close suppressed content and restore a space at the end of a block."""
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        elif tag in {"p", "li", "div"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        """Keep visible text only while outside suppressed script/style elements."""
        if not self.skip:
            self.parts.append(data)


def clean_text(value: str) -> str:
    """Strip HTML and contact patterns, then collapse whitespace for stable evidence offsets."""
    parser: PlainText = PlainText()
    parser.feed(value)
    text: str = html.unescape("".join(parser.parts))
    text = re.sub("[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub("(?<!\\w)\\+?\\d[\\d ()-]{7,}\\d(?!\\w)", "[phone removed]", text)
    return re.sub("\\s+", " ", text).strip()


def folded(value: str) -> str:
    """Fold case and accents for conservative multilingual title matching."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )


def role_family(title: str) -> str:
    """Return the first configured title-alias family, or the unclassified fallback."""
    title = folded(title)
    for role, spec in ROLES.items():
        if any(
            re.search("(?<!\\w)" + re.escape(folded(a)) + "(?!\\w)", title) for a in spec["aliases"]
        ):
            return role
    return "other"


PATTERNS: dict[str, re.Pattern[str]] = {
    key: re.compile(
        "(?<!\\w)(?:"
        + "|".join(re.escape(a) for a in sorted(item["aliases"], key=len, reverse=True))
        + ")(?!\\w)",
        re.IGNORECASE,
    )
    for key, item in SKILLS.items()
}


def extract_skills(text: str) -> list[SkillMention]:
    """Keep one evidence span per skill; optional/negated mentions still count as mentions."""
    result: list[SkillMention] = []
    for skill, pattern in PATTERNS.items():
        match: re.Match[str] | None = pattern.search(text)
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
