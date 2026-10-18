"""Deterministic mention extraction with exact evidence offsets into sanitized text."""

import html
import re
import unicodedata
from html.parser import HTMLParser

from careergraph.catalog import ROLES, SKILLS
from careergraph.contracts import SkillMention


class PlainText(HTMLParser):
    """Internal stateful HTML parser used only by clean_text.

    Its buffer and suppression depth change while parsing one input string. Normal callers should use clean_text rather than constructing this helper.
    """

    def __init__(self) -> None:
        """Initialize the internal HTML-to-text parser.

        Returns:
            None; creates an empty text buffer and suppression depth.

        Side effects:
            Changes this parser instance only. Normal callers use clean_text instead.
        """
        super().__init__()
        self.parts: list[str] = []
        self.skip: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle an opening HTML tag during sanitization.

        Args:
            tag: Lowercase tag name supplied by HTMLParser.
            attrs: Parsed attributes; deliberately ignored so links/contact attributes are not copied.

        Returns:
            None; updates the parser buffer or script/style suppression depth.

        Side effects:
            Mutates this parser instance; called by HTMLParser, not by the CLI.
        """
        if tag in {"script", "style"}:
            self.skip += 1
        elif tag in {"p", "br", "li", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        """Handle a closing HTML tag while preserving word boundaries.

        Args:
            tag: Lowercase closing tag supplied by HTMLParser.

        Returns:
            None; closes suppression or adds a separator for a block element.

        Side effects:
            Mutates this parser instance only.
        """
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        elif tag in {"p", "li", "div"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        """Retain visible text outside script and style elements.

        Args:
            data: Text fragment supplied by HTMLParser.

        Returns:
            None; appends visible data when suppression is inactive.

        Side effects:
            Mutates the internal parser buffer only.
        """
        if not self.skip:
            self.parts.append(data)


def clean_text(value: str) -> str:
    """Convert provider HTML into stable text for validation and evidence offsets.

    Args:
        value: An HTML or plain-text string from an advert field.

    Returns:
        Text with script/style content removed, contact patterns redacted and whitespace collapsed.

    Side effects:
        Uses a fresh parser; does not modify the caller's string or access the network.

    Example:
        clean_text("<p>Python <b>and SQL</b></p>") returns "Python and SQL".
    """
    parser: PlainText = PlainText()
    parser.feed(value)
    text: str = html.unescape("".join(parser.parts))
    text = re.sub("[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub("(?<!\\w)\\+?\\d[\\d ()-]{7,}\\d(?!\\w)", "[phone removed]", text)
    return re.sub("\\s+", " ", text).strip()


def folded(value: str) -> str:
    """Normalize case and accents for conservative title matching.

    Args:
        value: A title or configured alias.

    Returns:
        A casefolded string without combining accent marks.

    Example:
        folded("Ingénieur") returns "ingenieur".
    """
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )


def role_family(title: str) -> str:
    """Assign the first configured role family matching the advert title.

    Args:
        title: The advert title; the description is not used for this classification.

    Returns:
        A role ID such as data_engineer, or other when no title alias matches.

    Example:
        role_family("Senior Data Engineer") returns "data_engineer".
    """
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
    """Extract the first literal mention of each known skill.

    Args:
        text: Sanitized description; offsets refer to this exact string.

    Returns:
        One SkillMention per matched local skill: ID, start/end, matched text and bounded excerpt. End offsets are exclusive; no match gives an empty list.

    Side effects:
        No storage or network access. Optional and negated wording still counts as a mention.

    Example:
        extract_skills("NoSQL") returns []; SQL must match a complete configured alias.
    """
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
