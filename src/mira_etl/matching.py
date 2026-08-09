from __future__ import annotations

import re
import unicodedata

# Common legal-entity suffixes across the region (ES). Intentionally only
# strips WHOLE-WORD suffixes/patterns -- never partial substrings -- so it
# doesn't eat meaningful parts of a real company name.
LEGAL_SUFFIX_PATTERNS = [
    r"\bSOCIEDAD\s+AN[OÓ]NIMA\b",
    r"\bSOCIEDAD\s+DE\s+RESPONSABILIDAD\s+LIMITADA\b",
    r"\bSOCIEDAD\s+COLECTIVA\b",
    r"\bS\.?\s*A\.?\s*DE\s*C\.?\s*V\.?\b",
    r"\bS\.?\s*R\.?\s*L\.?\b",
    r"\bS\.?\s*A\.?\b",
    r"\bC\.?\s*A\.?\b",
    r"\bLTDA\.?\b",
    r"\bLIMITADA\b",
    r"\bCOMPA[ÑN]IA\b",
    r"\bCIA\.?\b",
    r"\bINC\.?\b",
    r"\bCORP\.?\b",
]


def normalise_name(value: str | None) -> str | None:
    """Uppercases, strips accents/punctuation, and drops common legal-entity
    suffixes, so the same company written with minor formatting differences
    ("Consultorias S.A." vs "CONSULTORIAS, SOCIEDAD ANONIMA") resolves to the
    same normalised string.

    This intentionally does NOT catch abbreviations, typos, or reordered
    words (e.g. "Const. del Norte" vs "Constructora del Norte") -- that is
    an accepted trade-off, see docs/entity_matching.md. Those cases get a
    new dimension row (match_method = 'UNMATCHED') rather than risk merging
    two different entities.
    """
    if not value:
        return None

    text = unicodedata.normalize("NFKD", value.upper())
    text = "".join(char for char in text if not unicodedata.combining(char))

    for pattern in LEGAL_SUFFIX_PATTERNS:
        text = re.sub(pattern, " ", text)

    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None
