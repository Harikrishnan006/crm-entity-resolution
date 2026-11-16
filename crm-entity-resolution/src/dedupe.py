#!/usr/bin/env python3
"""
Account de-duplication CLI.

Reads account and relationship CSVs, evaluates every candidate pair against
the rule layer, and writes a decision report. Nothing is merged: the output is
a recommendation with the rule that produced it, for a human to approve.

    python src/dedupe.py
    python src/dedupe.py --accounts data/accounts.csv --out report.csv
"""

import argparse
import csv
import os
import sys

from rules import KEEP, MERGE, REVIEW, cluster_merges, evaluate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ACCOUNTS = os.path.join(ROOT, "data", "accounts.csv")
DEFAULT_RELATIONSHIPS = os.path.join(ROOT, "data", "relationships.csv")

LABEL = {MERGE: "Merge", REVIEW: "Human Review", KEEP: "Keep"}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--accounts", default=DEFAULT_ACCOUNTS)
    ap.add_argument("--relationships", default=DEFAULT_RELATIONSHIPS)
    ap.add_argument("--out", default=None, help="write the report to CSV")
    args = ap.parse_args()

    for label, path in (("accounts", args.accounts),
                        ("relationships", args.relationships)):
        if not os.path.exists(path):
            print(f"ERROR: {label} file not found: {path}")
            print("       run 'python data/generate_sample_data.py' first")
            return 2

    accounts = read_csv(args.accounts)
    relationships = read_csv(args.relationships)
    results = evaluate(accounts, relationships)
    clusters = [c for c in cluster_merges(results) if c["size"] > 1]

    counts = {a: sum(1 for r in results if r["action"] == a)
              for a in (MERGE, REVIEW, KEEP)}
    print(f"\n{len(accounts)} accounts -> {len(results)} candidate pairs "
          f"(of {len(accounts) * (len(accounts) - 1) // 2} possible)\n")
    for action in (MERGE, REVIEW, KEEP):
        print(f"  {LABEL[action]:<14}{counts[action]}")

    print(f"\n{'Pair':<22}{'Score':>6}  {'Action':<15}{'Rule'}")
    print("-" * 56)
    for r in results:
        print(f"{r['account_a']}/{r['account_b']:<11}{r['score']:>6}  "
              f"{LABEL[r['action']]:<15}{r['rule']}")

    print("\nMerge groups (transitive):")
    if clusters:
        for c in clusters:
            others = [m for m in c["members"] if m != c["primary"]]
            print(f"  primary {c['primary']}  <- {', '.join(others)}")
    else:
        print("  none")

    print("\nEscalated to a human:")
    for r in results:
        if r["action"] == REVIEW:
            print(f"  [{r['rule']}] {r['account_a']} + {r['account_b']}")
            print(f"        {r['rationale']}")

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\nwrote {args.out}")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
