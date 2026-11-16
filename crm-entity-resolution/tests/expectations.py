"""
Expected outcome for every candidate pair in the sample dataset.

These are written from a reading of the records, independently of what the
resolver produces. The resolver is measured against this table, not the other
way round. When the two disagree the default assumption is that the resolver
is wrong - that is how the normaliser defect described in the README was
caught, and it would not have surfaced otherwise, because the wrong answer it
produced looked cautious and sensible.

Each entry: (account_a, account_b) -> (action, rule, why this is expected)
"""

from rules import KEEP, MERGE, REVIEW

EXPECTED_PAIRS = {
    ("ACC-001", "ACC-002"): (
        MERGE, "R6",
        "G1 clean duplicate: domain, external ref, legal name, headcount and "
        "city all agree, and ACC-002 is a thin import with no open pipeline."),
    ("ACC-003", "ACC-004"): (
        KEEP, "R2",
        "G2 parent and division: shared domain, but 820 vs 95 staff, separate "
        "external refs and each with its own open contract."),
    ("ACC-005", "ACC-006"): (
        REVIEW, "R3",
        "G3 rebrand: shared external ref and legal name say one entity, but "
        "the two domains conflict and neither is proven current."),
    ("ACC-007", "ACC-008"): (
        KEEP, "R1",
        "G4 name-similarity decoy: 'Harbor Lane' vs 'Harbour Lane' is a near "
        "match on name alone; domain, ref, legal name and city all differ."),
    ("ACC-009", "ACC-010"): (
        REVIEW, "R4",
        "G5 ownership conflict: identity is certain, but a live opportunity "
        "sits under a different owner and the related record says so."),
    ("ACC-011", "ACC-012"): (
        REVIEW, "R4",
        "G6 subsidiary ambiguity: shared domain, differing legal names, and "
        "identical headcount on two supposedly separate entities."),
    ("ACC-013", "ACC-014"): (
        MERGE, "R6", "G7 transitive cluster, pair 1 of 3."),
    ("ACC-013", "ACC-015"): (
        MERGE, "R6", "G7 transitive cluster, pair 2 of 3 (typo variant)."),
    ("ACC-014", "ACC-015"): (
        MERGE, "R6", "G7 transitive cluster, pair 3 of 3."),
}

# Pairs that must never reach the rule layer at all: blocking should drop them.
EXPECTED_NOT_CANDIDATES = [
    ("ACC-016", "ACC-017"),   # G8 shared head noun, otherwise unrelated
    ("ACC-018", "ACC-019"),   # G9 singletons
    ("ACC-001", "ACC-020"),
]

# Transitive merge groups, primary first.
EXPECTED_CLUSTERS = {
    "ACC-001": ["ACC-001", "ACC-002"],
    "ACC-013": ["ACC-013", "ACC-014", "ACC-015"],
}
