"""
Normalisation for account matching.

The only subtle decision in this module is which trailing words to strip.

Incorporation forms describe how a company is registered and carry no
identifying information: "Vireo Labs" and "Vireo Labs LLC" are the same
company. Those are stripped.

Words like Group, Holdings, Services, Partners, Capital and Integration look
like boilerplate but usually name a *different* legal entity - very often the
parent or a subsidiary of the one being compared. Stripping those merges
companies that should stay apart. An earlier version of this module stripped
them, which collapsed two distinct entities into one normalised identity and
silently disabled the rule meant to keep them separate. See README,
"A failure worth describing".
"""

import re
from difflib import SequenceMatcher

INCORPORATION_FORMS = {
    "inc", "incorporated", "llc", "ltd", "limited",
    "corp", "corporation", "lp", "llp", "plc", "gmbh", "bv", "pty",
}


def norm_name(value: str) -> str:
    """Lowercase, strip punctuation, drop trailing incorporation forms."""
    if not isinstance(value, str):
        return ""
    tokens = [t for t in re.sub(r"[^a-z0-9 ]", " ", value.lower()).split() if t]
    while tokens and tokens[-1] in INCORPORATION_FORMS:
        tokens.pop()
    return "".join(tokens)


def norm_domain(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"^www\.", "", value.strip().lower())


def norm_ref(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def name_similarity(a: str, b: str) -> float:
    """Character-level ratio on normalised names. 0.0 if either is empty."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def headcount_differs(a, b, threshold: float = 0.20) -> bool:
    """
    True only when both values are known and materially apart.

    A missing headcount is unknown, never evidence. Returning True for a blank
    would let absent data argue that two records are different companies.
    """
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    larger = max(a, b)
    if larger == 0:
        return False
    return abs(a - b) / larger > threshold
