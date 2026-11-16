"""
Run with:  pytest -v
"""

import csv
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from expectations import (EXPECTED_CLUSTERS, EXPECTED_NOT_CANDIDATES,
                          EXPECTED_PAIRS)
from normalise import headcount_differs, name_similarity, norm_name
from rules import MERGE, cluster_merges, evaluate, is_candidate, prepare


def read_csv(name):
    path = os.path.join(ROOT, "data", name)
    if not os.path.exists(path):
        pytest.skip("sample data missing - run data/generate_sample_data.py")
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def accounts():
    return read_csv("accounts.csv")


@pytest.fixture(scope="module")
def results(accounts):
    return evaluate(accounts, read_csv("relationships.csv"))


@pytest.fixture(scope="module")
def by_pair(results):
    return {(r["account_a"], r["account_b"]): r for r in results}


# --------------------------------------------------------------- decisions --

@pytest.mark.parametrize("pair", sorted(EXPECTED_PAIRS))
def test_pair_decision_matches_expectation(pair, by_pair):
    action, rule, why = EXPECTED_PAIRS[pair]
    assert pair in by_pair, f"{pair} produced no decision. {why}"
    actual = by_pair[pair]
    assert (actual["action"], actual["rule"]) == (action, rule), (
        f"{pair}: expected {action} via {rule}, "
        f"got {actual['action']} via {actual['rule']}. {why}")


def test_no_unexpected_pairs(by_pair):
    assert set(by_pair) == set(EXPECTED_PAIRS), (
        "candidate pairs changed; update expectations deliberately, "
        "never to match new output")


@pytest.mark.parametrize("pair", EXPECTED_NOT_CANDIDATES)
def test_unrelated_accounts_are_blocked(pair, accounts):
    index = {a["account_id"]: prepare(a) for a in accounts}
    assert not is_candidate(index[pair[0]], index[pair[1]]), (
        f"{pair} should not survive blocking")


# ---------------------------------------------------------------- clusters --

def test_transitive_clusters(results):
    clusters = {c["primary"]: c["members"]
                for c in cluster_merges(results) if c["size"] > 1}
    assert clusters == EXPECTED_CLUSTERS


def test_primary_is_lowest_id(results):
    for c in cluster_merges(results):
        assert c["primary"] == min(c["members"])


def test_nothing_merged_under_an_escalation_rule(results):
    offenders = [r for r in results
                 if r["action"] == MERGE and r["rule"] in {"R3", "R4", "R5"}]
    assert not offenders, f"merge recommended despite escalation: {offenders}"


def test_every_decision_names_a_rule(results):
    assert all(r["rule"] and r["rationale"] for r in results)


# ------------------------------------------------------------ normalisation --

def test_incorporation_forms_are_stripped():
    assert norm_name("Vireo Labs LLC") == norm_name("Vireo Labs")
    assert norm_name("Juniper Freight Inc.") == norm_name("Juniper Freight")


def test_entity_words_are_not_stripped():
    """
    Regression test for the defect described in the README.

    An earlier normaliser stripped Group and Holdings as boilerplate, which
    collapsed a company and its parent into one identity and disabled the rule
    that keeps them apart. These must stay distinct.
    """
    assert norm_name("Caldera Inc") != norm_name("Caldera Group Holdings")
    assert norm_name("Orrery Systems") != norm_name("Orrery Systems Integration")
    assert norm_name("Harbor Lane") != norm_name("Harbor Lane Capital")


def test_blank_headcount_is_unknown_not_evidence():
    assert headcount_differs(None, 500) is False
    assert headcount_differs("", 500) is False
    assert headcount_differs(500, 95) is True
    assert headcount_differs(500, 480) is False


def test_name_similarity_bounds():
    assert name_similarity("", "anything") == 0.0
    assert name_similarity("juniperfreight", "juniperfreight") == 1.0
