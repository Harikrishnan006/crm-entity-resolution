#!/usr/bin/env python3
"""
Generates the synthetic CRM dataset used by the resolver and its tests.

Every record is invented. The company names, domains and identifiers do not
correspond to any real organisation. What is realistic is the *shape* of the
mess: each group below reproduces a failure mode that shows up in real CRM
data, and the point of the dataset is that several of them look identical to a
naive matcher while requiring opposite decisions.

Trap categories represented:

  G1  Clean duplicate          every identifier agrees, one record is a thin import
  G2  Parent and division      shared domain, separate legal entities and contracts
  G3  Rebrand                  one entity, two domains, neither proven current
  G4  Name-similarity decoy    0.97 name match, every other identifier differs
  G5  Ownership conflict       identity certain, live deal under a different owner
  G6  Subsidiary ambiguity     shared domain, differing legal names, no corroboration
  G7  Transitive cluster       three records of one entity, no single pair obvious
  G8  Shared head noun         same first word, unrelated companies
  G9  Singleton                no candidate pair at all

Run:  python data/generate_sample_data.py
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# account_id, name, domain, owner, employees, city, legal_name, open_opps,
# last_activity, external_ref, notes
ACCOUNTS = [
    # --- G1: clean duplicate -------------------------------------------------
    ("ACC-001", "Vireo Labs", "vireolabs.test", "dana", 410, "Boise",
     "Vireo Labs LLC", 1, "2027-02-09", "VR-500", "Primary site"),
    ("ACC-002", "Vireo Laboratories", "vireolabs.test", "ravi", 410, "Boise",
     "Vireo Labs LLC", 0, "2027-02-11", "VR-500", "Imported from event list"),

    # --- G2: parent and division --------------------------------------------
    ("ACC-003", "Caldera Group", "caldera.test", "dana", 820, "Reno",
     "Caldera Group Inc", 1, "2027-02-03", "CG-21", "Parent account"),
    ("ACC-004", "Caldera Field Services", "caldera.test", "ravi", 95, "Reno",
     "Caldera Field Services LLC", 1, "2027-02-12", "CG-22",
     "Division, separate contract"),

    # --- G3: rebrand ---------------------------------------------------------
    ("ACC-005", "Pinewood Signal", "pinewoodsignal.test", "dana", 260, "Tulsa",
     "Pinewood Signal Inc", 1, "2027-02-10", "PW-07", "Call analytics vendor"),
    ("ACC-006", "Pinewood Audio", "pinewoodaudio.test", "ravi", 260, "Tulsa",
     "Pinewood Signal Inc", 0, "2027-02-06", "PW-07",
     "Rebrand mentioned during import"),

    # --- G4: name-similarity decoy ------------------------------------------
    ("ACC-007", "Harbor Lane Capital", "harborlane.test", "dana", 70, "Omaha",
     "Harbor Lane Capital LLC", 0, "2027-01-29", "HL-33", "Distinct business"),
    ("ACC-008", "Harbour Lane Capital", "harbourlanecap.test", "ravi", 70,
     "Des Moines", "Harbour Lane Capital Ltd", 0, "2027-01-28", "HLC-91",
     "Name similarity only"),

    # --- G5: ownership conflict ---------------------------------------------
    ("ACC-009", "Tessellate Retail", "tessellate.test", "dana", 150, "Mesa",
     "Tessellate Retail LLC", 0, "2027-02-13", "TS-18", "Marketing sourced"),
    ("ACC-010", "Tesselate Retail", "tessellate.test", "ravi", 150, "Mesa",
     "Tessellate Retail LLC", 1, "2027-02-02", "TS-18",
     "Owner differs; live deal"),

    # --- G6: subsidiary ambiguity -------------------------------------------
    ("ACC-011", "Orrery Systems", "orrery.test", "dana", 540, "Akron",
     "Orrery Systems Corp", 0, "2027-02-11", "OR-60", "Enterprise account"),
    ("ACC-012", "Orrery Systems Integration", "orrery.test", "ravi", 540,
     "Akron", "Orrery Systems Integration LLC", 0, "2027-02-08", "OR-61",
     "Subsidiary? shared domain"),

    # --- G7: transitive cluster of three ------------------------------------
    ("ACC-013", "Juniper Freight", "juniperfreight.test", "dana", 300,
     "Spokane", "Juniper Freight Inc", 1, "2027-02-07", "JF-12", "Main record"),
    ("ACC-014", "Juniper Freight Inc.", "juniperfreight.test", "ravi", 300,
     "Spokane", "Juniper Freight Inc", 0, "2027-02-01", "JF-12",
     "Created by sales"),
    ("ACC-015", "Juniper Frieght", "juniperfreight.test", "dana", 300,
     "Spokane", "Juniper Freight Inc", 0, "2027-01-30", "JF-12",
     "Typo on web form"),

    # --- G8: shared head noun, unrelated ------------------------------------
    ("ACC-016", "Quillon Analytics", "quillonanalytics.test", "dana", 120,
     "Fargo", "Quillon Analytics LLC", 1, "2027-02-05", "QA-04",
     "Data tooling"),
    ("ACC-017", "Quillon Biosciences", "quillonbio.test", "ravi", 640,
     "Madison", "Quillon Biosciences Inc", 1, "2027-02-04", "QB-77",
     "Unrelated to QA-04"),

    # --- G9: singletons ------------------------------------------------------
    ("ACC-018", "Marrow Pike Logistics", "marrowpike.test", "dana", 45,
     "Duluth", "Marrow Pike Logistics LLC", 0, "2027-01-26", "MP-01", ""),
    ("ACC-019", "Beacon Hollow Media", "beaconhollow.test", "ravi", 210,
     "Lubbock", "Beacon Hollow Media Inc", 1, "2027-02-09", "BH-15", ""),
    ("ACC-020", "Saltmarsh Interiors", "saltmarsh.test", "dana", 33, "Erie",
     "Saltmarsh Interiors LLC", 0, "2027-01-22", "SM-08", ""),
]

ACCOUNT_HEADER = ["account_id", "name", "domain", "owner", "employees", "city",
                  "legal_name", "open_opps", "last_activity", "external_ref",
                  "notes"]

# relationship_id, account_id, record_type, related_id, status, owner, risk_note
RELATIONSHIPS = [
    ("REL-001", "ACC-001", "opportunity", "OPP-900", "open", "dana", "retain stage and owner"),
    ("REL-002", "ACC-002", "contact", "CON-700", "active", "ravi", "possible duplicate contact"),
    ("REL-003", "ACC-003", "opportunity", "OPP-901", "open", "dana", "separate legal contract"),
    ("REL-004", "ACC-004", "opportunity", "OPP-902", "open", "ravi", "separate legal contract"),
    ("REL-005", "ACC-005", "opportunity", "OPP-903", "open", "dana", "may survive rebrand"),
    ("REL-006", "ACC-006", "activity", "ACT-800", "complete", "ravi", "validate rebrand"),
    ("REL-007", "ACC-007", "activity", "ACT-801", "complete", "dana", "different business"),
    ("REL-008", "ACC-008", "activity", "ACT-802", "complete", "ravi", "different business"),
    ("REL-009", "ACC-009", "contact", "CON-701", "active", "dana", "retain"),
    ("REL-010", "ACC-010", "opportunity", "OPP-904", "open", "ravi", "owner conflict"),
    ("REL-011", "ACC-011", "contact", "CON-702", "active", "dana", "check entity boundary"),
    ("REL-012", "ACC-012", "contact", "CON-703", "active", "ravi", "potential subsidiary"),
    ("REL-013", "ACC-013", "opportunity", "OPP-905", "open", "dana", "retain"),
    ("REL-014", "ACC-014", "activity", "ACT-803", "complete", "ravi", "retain"),
    ("REL-015", "ACC-015", "activity", "ACT-804", "complete", "dana", "retain"),
    ("REL-016", "ACC-016", "opportunity", "OPP-906", "open", "dana", "retain"),
    ("REL-017", "ACC-017", "opportunity", "OPP-907", "open", "ravi", "retain"),
    ("REL-018", "ACC-019", "opportunity", "OPP-908", "open", "ravi", "retain"),
]

RELATIONSHIP_HEADER = ["relationship_id", "account_id", "record_type",
                       "related_id", "status", "owner", "risk_note"]

# lead_id, account_id, role, icp_fit, email_status, phone_status,
# duplicate_flag, outreach_status
LEADS = [
    ("LEAD-01", "ACC-001", "Operations VP", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-02", "ACC-001", "Head of Revenue", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-03", "ACC-003", "Procurement Lead", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-04", "ACC-003", "Operations VP", "strong", "verified", "missing", "no", "not_started"),
    ("LEAD-05", "ACC-004", "Field Ops Manager", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-06", "ACC-005", "Contact Centre Director", "strong", "verified", "verified", "possible", "not_started"),
    ("LEAD-07", "ACC-007", "CFO", "weak", "verified", "verified", "no", "not_started"),
    ("LEAD-08", "ACC-009", "Demand Gen Manager", "strong", "unverified", "verified", "no", "not_started"),
    ("LEAD-09", "ACC-010", "Head of Retail Ops", "strong", "verified", "verified", "possible", "not_started"),
    ("LEAD-10", "ACC-013", "Logistics Director", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-11", "ACC-013", "Logistics Director", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-12", "ACC-013", "Logistics Director", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-13", "ACC-013", "Fleet Manager", "strong", "verified", "verified", "no", "active"),
    ("LEAD-14", "ACC-016", "Head of Analytics", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-15", "ACC-016", "Data Platform Lead", "strong", "missing", "missing", "no", "not_started"),
    ("LEAD-16", "ACC-017", "Lab Operations Lead", "weak", "verified", "verified", "no", "not_started"),
    ("LEAD-17", "ACC-018", "Owner", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-18", "ACC-019", "Marketing Director", "strong", "verified", "verified", "no", "active"),
    ("LEAD-19", "ACC-019", "Head of Content", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-20", "ACC-020", "Studio Manager", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-21", "ACC-011", "IT Director", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-22", "ACC-012", "Services Director", "strong", "verified", "verified", "no", "not_started"),
    ("LEAD-23", "ACC-006", "Audio Engineering Lead", "strong", "verified", "verified", "possible", "not_started"),
    ("LEAD-24", "ACC-020", "Studio Manager", "strong", "verified", "verified", "no", "not_started"),
]

LEAD_HEADER = ["lead_id", "account_id", "role", "icp_fit", "email_status",
               "phone_status", "duplicate_flag", "outreach_status"]

# rep_id, name, active_leads, overdue_tasks, max_additional, coverage
REPS = [
    ("REP-A", "dana", 28, 1, 35, "low"),
    ("REP-B", "ravi", 88, 19, 12, "high"),
]
REP_HEADER = ["rep_id", "name", "active_leads", "overdue_tasks",
              "max_additional", "coverage"]


def write(filename, header, rows):
    path = os.path.join(HERE, filename)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"wrote {path}  ({len(rows)} rows)")


if __name__ == "__main__":
    write("accounts.csv", ACCOUNT_HEADER, ACCOUNTS)
    write("relationships.csv", RELATIONSHIP_HEADER, RELATIONSHIPS)
    write("leads.csv", LEAD_HEADER, LEADS)
    write("reps.csv", REP_HEADER, REPS)
