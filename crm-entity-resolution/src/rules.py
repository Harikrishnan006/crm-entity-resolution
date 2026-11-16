"""
The decision layer.

A single similarity score cannot express "this piece of evidence is
disqualifying regardless of how much other evidence agrees". A shared domain
between two differently-named legal entities is exactly that: strong evidence
of a relationship and no evidence at all of identity.

So the decision is made by ordered rules, and the score is only consulted when
no rule has fired. Distinctness rules run first, so that genuinely separate
companies are never escalated or merged on the strength of a shared domain or
a near-identical name. Each decision reports the rule that produced it, which
is what makes the output reviewable by the person who has to execute it.
"""

import re

from normalise import (headcount_differs, name_similarity, norm_domain,
                       norm_name, norm_ref)

KEEP, MERGE, REVIEW = "keep", "merge", "human_review"

# Signal weights. External reference is the strongest because two rows sharing
# one trace to the same upstream source record.
W_EXTERNAL_REF = 40
W_DOMAIN = 25
W_LEGAL_NAME = 25
W_NAME_STRONG = 15
W_NAME_PARTIAL = 8
W_CITY = 5
W_HEADCOUNT = 5

NAME_STRONG = 0.85
NAME_PARTIAL = 0.70
MERGE_THRESHOLD = 70
REVIEW_THRESHOLD = 45

# Free-text notes on related records that mark an unresolved conflict.
# Deliberately narrow. Broad keywords such as "check" or "different" fired on
# notes that were merely descriptive and produced false escalations.
CONFLICT_PATTERNS = [
    r"\bconflict\b",
    r"\bvalidate\b",
    r"check entity\b",
    r"potential subsidiary\b",
    r"different entity\b",
]


def prepare(account: dict) -> dict:
    """Attach normalised fields to a raw account row."""
    return {
        **account,
        "_name": norm_name(account.get("name", "")),
        "_domain": norm_domain(account.get("domain", "")),
        "_ref": norm_ref(account.get("external_ref", "")),
        "_legal": norm_name(account.get("legal_name", "")),
    }


def index_relationships(relationships) -> dict:
    """account_id -> {open_opps, conflict_notes}"""
    index = {}
    for row in relationships:
        entry = index.setdefault(row["account_id"],
                                 {"open_opps": 0, "conflict_notes": []})
        if (row.get("record_type") == "opportunity"
                and row.get("status") == "open"):
            entry["open_opps"] += 1
        note = (row.get("risk_note") or "").lower()
        if any(re.search(p, note) for p in CONFLICT_PATTERNS):
            entry["conflict_notes"].append(row["risk_note"])
    return index


def is_candidate(a: dict, b: dict) -> bool:
    """
    Blocking. Only pairs sharing at least one real connecting signal are
    compared, so unrelated companies never reach the rules at all.
    """
    return bool(
        (a["_domain"] and a["_domain"] == b["_domain"])
        or (a["_ref"] and a["_ref"] == b["_ref"])
        or (a["_legal"] and a["_legal"] == b["_legal"])
        or name_similarity(a["_name"], b["_name"]) >= NAME_PARTIAL
    )


def score_pair(a: dict, b: dict):
    """Weighted evidence score. Returns (score, signals)."""
    score, signals = 0, []
    if a["_ref"] and a["_ref"] == b["_ref"]:
        score += W_EXTERNAL_REF
        signals.append("external ref match")
    if a["_domain"] and a["_domain"] == b["_domain"]:
        score += W_DOMAIN
        signals.append("domain match")
    if a["_legal"] and a["_legal"] == b["_legal"]:
        score += W_LEGAL_NAME
        signals.append("legal name match")

    sim = name_similarity(a["_name"], b["_name"])
    if sim >= NAME_STRONG:
        score += W_NAME_STRONG
        signals.append(f"name similarity {sim:.2f}")
    elif sim >= NAME_PARTIAL:
        score += W_NAME_PARTIAL
        signals.append(f"partial name similarity {sim:.2f}")

    if a.get("city") and a.get("city") == b.get("city"):
        score += W_CITY
        signals.append("same city")
    if a.get("employees") and a.get("employees") == b.get("employees"):
        score += W_HEADCOUNT
        signals.append("same headcount")
    return score, signals


def decide(a: dict, b: dict, score: int, rels: dict):
    """Ordered rules. First match wins. Returns (action, rule_id, rationale)."""
    ra = rels.get(a["account_id"], {"open_opps": 0, "conflict_notes": []})
    rb = rels.get(b["account_id"], {"open_opps": 0, "conflict_notes": []})

    legal_differs = a["_legal"] != b["_legal"]
    domain_differs = bool(a["_domain"]) and bool(b["_domain"]) and a["_domain"] != b["_domain"]
    ref_differs = a["_ref"] != b["_ref"]
    shared_domain = bool(a["_domain"]) and a["_domain"] == b["_domain"]

    # R1 - nothing identifying is shared. Similar names are not evidence.
    if legal_differs and domain_differs and ref_differs:
        return KEEP, "R1", (
            "Different legal name, different domain and different external "
            "reference. Name similarity alone is not evidence of one entity.")

    # R2 - shared domain, but separate operations are corroborated
    if shared_domain and legal_differs:
        corroborated = (
            headcount_differs(a.get("employees"), b.get("employees"))
            and ref_differs
            and ra["open_opps"] >= 1
            and rb["open_opps"] >= 1
        )
        if corroborated:
            return KEEP, "R2", (
                "Shared domain but distinct legal names, materially different "
                "headcount, separate external references and separate open "
                "pipeline. Consistent with a parent and a division: link them, "
                "do not merge.")

    # R3 - identity likely shared, but which domain is current is unresolved
    if domain_differs and (not ref_differs or not legal_differs):
        return REVIEW, "R3", (
            "A shared external reference and/or legal name indicates one "
            "entity, but the records carry different domains. Merging would "
            "propagate a possibly dead domain into every downstream send.")

    # R4 - a related record carries an explicit unresolved-conflict note
    notes = ra["conflict_notes"] + rb["conflict_notes"]
    if notes:
        return REVIEW, "R4", (
            "Related records carry unresolved conflict notes: "
            + "; ".join(sorted(set(notes))))

    # R5 - shared domain, differing legal names, nothing corroborating either way
    if shared_domain and legal_differs:
        return REVIEW, "R5", (
            "Shared domain with differing legal names and no independent "
            "evidence of separate operations. A shared domain is a signal, "
            "not proof.")

    # R6 / R7 / R8 - score-driven fallback
    if score >= MERGE_THRESHOLD:
        return MERGE, "R6", (
            f"Multiple independent identifiers agree (score {score}) with no "
            "unresolved conflict.")
    if score >= REVIEW_THRESHOLD:
        return REVIEW, "R7", (
            f"Partial evidence only (score {score}); needs a human read.")
    return KEEP, "R8", (
        f"Insufficient evidence of a shared entity (score {score}).")


def evaluate(accounts, relationships):
    """Evaluate every candidate pair. Returns a list of decision dicts."""
    prepared = [prepare(a) for a in accounts]
    rels = index_relationships(relationships)

    results = []
    for i, a in enumerate(prepared):
        for b in prepared[i + 1:]:
            if not is_candidate(a, b):
                continue
            score, signals = score_pair(a, b)
            action, rule, rationale = decide(a, b, score, rels)
            results.append({
                "account_a": a["account_id"], "name_a": a["name"],
                "account_b": b["account_id"], "name_b": b["name"],
                "score": score,
                "signals": "; ".join(signals) or "none",
                "action": action,
                "rule": rule,
                "rationale": rationale,
            })
    return sorted(results, key=lambda r: (-r["score"], r["account_a"]))


def cluster_merges(results):
    """
    Group merge decisions transitively.

    Pairwise matching alone reports three duplicate records as three separate
    pairs, which invites three separate merges and a different surviving ID
    each time. Union-find collapses them into one group with one primary. The
    primary is the lowest account ID: the oldest surviving record, chosen by a
    stable rule rather than by recency, which a rebrand can make misleading.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    for r in results:
        if r["action"] == MERGE:
            union(r["account_a"], r["account_b"])

    groups = {}
    for node in parent:
        groups.setdefault(find(node), set()).add(node)

    return [{"primary": primary, "members": sorted(members),
             "size": len(members)}
            for primary, members in sorted(groups.items())]
