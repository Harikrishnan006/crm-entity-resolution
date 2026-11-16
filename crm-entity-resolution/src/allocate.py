#!/usr/bin/env python3
"""
Capacity-aware lead routing.

Classifies leads for outreach readiness and distributes the ready ones across
reps without exceeding stated capacity. It reads the resolver's output, so a
lead sitting on an account whose identity is still unresolved is held rather
than contacted - otherwise two reps work the same company under two records.

Two readings of readiness are produced for every lead:

  flag_literal  the stated fields only (icp_fit, duplicate_flag, contact
                status, outreach status), taking the CRM at its word
  recommended   the same, plus one inference: the same role appearing more
                than once at the same account is treated as a contact-level
                duplicate even when the duplicate flag says otherwise

Where the two disagree, the lead carries a note naming the difference. A
judgement folded silently into a headline number looks like a fact to everyone
downstream; stated beside the alternative, it is something a reviewer can
accept or reject in seconds.

    python src/allocate.py
"""

import argparse
import csv
import os
import sys

from rules import MERGE, REVIEW, cluster_merges, evaluate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")

READY, ENRICH, DUP, EXCLUDE = ("ready", "enrichment_needed",
                               "duplicate_review", "exclude")
LABEL = {READY: "Ready", ENRICH: "Enrichment", DUP: "Duplicate review",
         EXCLUDE: "Exclude"}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def contact_gaps(lead):
    gaps = []
    if lead["email_status"] != "verified":
        gaps.append(f"email {lead['email_status']}")
    if lead["phone_status"] != "verified":
        gaps.append(f"phone {lead['phone_status']}")
    return gaps


def classify_flag_literal(lead):
    """The CRM's own fields, taken at face value."""
    if lead["icp_fit"] == "weak":
        return EXCLUDE
    if lead["duplicate_flag"] == "possible":
        return DUP
    if lead["outreach_status"] == "active":
        return EXCLUDE
    if contact_gaps(lead):
        return ENRICH
    return READY


def classify(lead, unresolved_accounts, role_seen_at):
    """The recommended reading, with cross-sheet and role-repeat inference."""
    if lead["icp_fit"] == "weak":
        return EXCLUDE, "Weak ICP fit; no enrichment would make this eligible."

    reasons = []
    if lead["duplicate_flag"] == "possible":
        reasons.append("duplicate flag is 'possible'")
    if lead["account_id"] in unresolved_accounts:
        reasons.append(f"account {lead['account_id']} is unresolved in the "
                       "entity-resolution review queue")
    first = role_seen_at.get((lead["account_id"], lead["role"]))
    if first and first != lead["lead_id"]:
        reasons.append(f"role '{lead['role']}' already present at "
                       f"{lead['account_id']} on {first}")
    if reasons:
        if lead["outreach_status"] == "active":
            reasons.append("already in active outreach")
        if contact_gaps(lead):
            reasons.append("contact data also incomplete")
        return DUP, "Hold for review: " + "; ".join(reasons) + "."

    if lead["outreach_status"] == "active":
        return EXCLUDE, ("Already in active outreach; excluded from this "
                         "allocation round, not from the pipeline.")

    gaps = contact_gaps(lead)
    if gaps:
        return ENRICH, f"Contact data incomplete ({', '.join(gaps)})."

    return READY, "Strong ICP, contact verified, no duplicate signal."


def allocate(ready_leads, reps):
    """
    Fill from the least loaded rep first, and never use the full headroom of a
    rep carrying an overdue backlog. Stated capacity is a ceiling, not a
    target: adding volume to a rep with a backlog produces more backlog, not
    more outreach.
    """
    budget = {}
    for rep in reps:
        headroom = int(rep["max_additional"])
        overdue = int(rep["overdue_tasks"])
        if overdue >= 10:
            headroom = 0
            note = f"held at zero: {overdue} overdue tasks"
        elif overdue > 0:
            headroom = max(0, headroom - overdue)
            note = f"headroom reduced by {overdue} overdue tasks"
        else:
            note = "full headroom available"
        budget[rep["name"]] = {"left": headroom, "note": note,
                               "load": int(rep["active_leads"])}

    order = sorted(budget, key=lambda n: budget[n]["load"])
    assignments = {}
    for lead in ready_leads:
        for name in order:
            if budget[name]["left"] > 0:
                assignments[lead["lead_id"]] = name
                budget[name]["left"] -= 1
                break
    return assignments, budget


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leads", default=os.path.join(D, "leads.csv"))
    ap.add_argument("--reps", default=os.path.join(D, "reps.csv"))
    ap.add_argument("--accounts", default=os.path.join(D, "accounts.csv"))
    ap.add_argument("--relationships", default=os.path.join(D, "relationships.csv"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    for path in (args.leads, args.reps, args.accounts, args.relationships):
        if not os.path.exists(path):
            print(f"ERROR: file not found: {path}")
            print("       run 'python data/generate_sample_data.py' first")
            return 2

    leads = read_csv(args.leads)
    reps = read_csv(args.reps)
    results = evaluate(read_csv(args.accounts), read_csv(args.relationships))

    unresolved = {acct for r in results if r["action"] == REVIEW
                  for acct in (r["account_a"], r["account_b"])}
    merged_away = {m for c in cluster_merges(results) if c["size"] > 1
                   for m in c["members"] if m != c["primary"]}
    unresolved |= merged_away

    role_seen_at = {}
    for lead in sorted(leads, key=lambda l: l["lead_id"]):
        role_seen_at.setdefault((lead["account_id"], lead["role"]),
                                lead["lead_id"])

    rows = []
    for lead in leads:
        action, reason = classify(lead, unresolved, role_seen_at)
        literal = classify_flag_literal(lead)
        rows.append({**lead, "action": action, "action_flag_literal": literal,
                     "assigned_to": "", "reason": reason,
                     "divergence": ("" if literal == action
                                    else f"flag-literal reading: {literal}")})

    ready = [r for r in rows if r["action"] == READY]
    assignments, budget = allocate(ready, reps)
    for row in rows:
        row["assigned_to"] = assignments.get(row["lead_id"], "")

    counts = {a: sum(1 for r in rows if r["action"] == a)
              for a in (READY, ENRICH, DUP, EXCLUDE)}
    literal_ready = sum(1 for r in rows if r["action_flag_literal"] == READY)

    print(f"\n{len(leads)} leads\n")
    for a in (READY, ENRICH, DUP, EXCLUDE):
        print(f"  {LABEL[a]:<18}{counts[a]}")
    print(f"\n  ready, recommended reading : {counts[READY]}")
    print(f"  ready, flag-literal reading: {literal_ready}")
    diverged = [r for r in rows if r["divergence"]]
    print(f"  leads where the two differ : {len(diverged)}"
          + (f"  ({', '.join(r['lead_id'] for r in diverged)})" if diverged else ""))

    print("\nCapacity:")
    for rep in reps:
        b = budget[rep["name"]]
        used = sum(1 for r in rows if r["assigned_to"] == rep["name"])
        print(f"  {rep['name']:<8}assigned {used:<3} "
              f"(stated headroom {rep['max_additional']}, {b['note']})")

    print("\nAssigned:")
    for r in rows:
        if r["assigned_to"]:
            print(f"  {r['lead_id']}  {r['account_id']}  -> {r['assigned_to']}")

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {args.out}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
