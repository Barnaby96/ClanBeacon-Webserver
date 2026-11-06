"""Regression tests for verified OSRS skill bypasses."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from utils.osrs_verified_bypass import (
    VerifiedBypassError,
    effective_skills_with_verified_bypasses,
)


def proposal_for(quest_id):
    data = json.loads(
        Path(
            "data/osrs_requirement_proposals_v1.json"
        ).read_text(encoding="utf-8-sig")
    )
    matches = [
        item
        for item in data["proposals"]
        if item["quest_id"] == quest_id
    ]
    assert len(matches) == 1
    return matches[0]


@pytest.fixture
def temple():
    proposal = proposal_for("temple_of_ikov")
    assert proposal["wiki_revision"] == 15363124
    return proposal


@pytest.fixture
def reviewed_temple(temple):
    refs = [
        "https://oldschool.runescape.wiki/w/Temple_of_Ikov",
        (
            "https://oldschool.runescape.wiki/w/"
            "Temple_of_Ikov#Fire_Warrior_of_Lesarkus"
        ),
    ]

    text = temple["requirements_wikitext"]

    exception = {
        "quest_id": "temple_of_ikov",
        "skill": "ranged",
        "source_level": 40,
        "source_boostability": "no",
        "source_line": 2,
        "source_text": text.splitlines()[1],
        "source_wikitext_sha256": hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest(),
        "wiki_revision": 15363124,
        "verification_decision": "VERIFIED_ACCESSIBLE_BYPASS",
        "alternative_route": (
            "Use suitable darts or throwing knives "
            "against the Fire Warrior."
        ),
        "alternative_skill_requirements": {},
        "non_skill_conditions": [
            "Suitable throwing weapons",
            "Required ice-arrow equipment condition",
        ],
        "evidence_refs": refs,
    }

    return {
        "reviewer_evidence_refs": refs,
        "review_findings": [
            {
                "code": "VERIFIED_ACCESSIBLE_BYPASS",
                "source_line": 2,
                "status": "RESOLVED",
                "resolution": (
                    "Verified alternative avoids "
                    "the 40 Ranged threshold."
                ),
                "resolution_evidence_refs": refs,
            },
        ],
        "verified_bypass_exceptions": [exception],
    }


def test_valid_bypass_preserves_original_source(
    temple, reviewed_temple
):
    before_proposal = copy.deepcopy(temple)
    before_review = copy.deepcopy(reviewed_temple)

    skills, boosts, omitted = (
        effective_skills_with_verified_bypasses(
            temple, reviewed_temple
        )
    )

    assert skills == {"thieving": 42}
    assert boosts == {"thieving": "yes"}
    assert omitted == ("ranged",)
    assert temple == before_proposal
    assert reviewed_temple == before_review

    source_skills = {
        item["skill"]: item["level"]
        for item in temple["observations"]["skills"]["skills"]
    }
    assert source_skills == {
        "thieving": 42,
        "ranged": 40,
    }


def test_without_bypass_retains_original_skills(temple):
    review = {
        "reviewer_evidence_refs": [],
        "review_findings": [],
    }

    skills, boosts, omitted = (
        effective_skills_with_verified_bypasses(
            temple, review
        )
    )

    assert skills == {"thieving": 42, "ranged": 40}
    assert boosts == {"thieving": "yes", "ranged": "no"}
    assert omitted == ()


def test_unconditional_family_crest_unchanged():
    proposal = proposal_for("family_crest")
    review = {
        "reviewer_evidence_refs": [],
        "review_findings": [],
    }

    skills, boosts, omitted = (
        effective_skills_with_verified_bypasses(
            proposal, review
        )
    )

    assert skills == {
        "mining": 40,
        "smithing": 40,
        "magic": 59,
        "crafting": 40,
    }
    assert set(boosts.values()) == {"yes"}
    assert set(boosts) == set(skills)
    assert omitted == ()


def test_appended_source_line_rejected(temple, reviewed_temple):
    altered = copy.deepcopy(temple)
    altered["requirements_wikitext"] += (
        "\n* Invented requirement"
    )

    with pytest.raises(VerifiedBypassError):
        effective_skills_with_verified_bypasses(
            altered, reviewed_temple
        )


def test_changed_combat_source_rejected(
    temple, reviewed_temple
):
    altered = copy.deepcopy(temple)
    original_text = altered["requirements_wikitext"]

    altered["requirements_wikitext"] = (
        original_text.replace("level 84", "level 85")
    )

    assert altered["requirements_wikitext"] != original_text

    with pytest.raises(VerifiedBypassError):
        effective_skills_with_verified_bypasses(
            altered, reviewed_temple
        )


def test_changed_conditional_observation_rejected(
    temple, reviewed_temple
):
    altered = copy.deepcopy(temple)
    altered["observations"]["skills"][
        "conditional_skill_lines"
    ][0]["needs_review"] = False

    with pytest.raises(VerifiedBypassError):
        effective_skills_with_verified_bypasses(
            altered, reviewed_temple
        )


def test_wrong_source_fingerprint_rejected(
    temple, reviewed_temple
):
    review = copy.deepcopy(reviewed_temple)
    review["verified_bypass_exceptions"][0][
        "source_wikitext_sha256"
    ] = "0" * 64

    with pytest.raises(VerifiedBypassError):
        effective_skills_with_verified_bypasses(
            temple, review
        )


@pytest.mark.parametrize(
    "case",
    [
        "unknown_skill",
        "incorrect_level",
        "incorrect_boostability",
        "incorrect_line",
        "incorrect_text",
        "incorrect_revision",
        "incorrect_quest",
        "unverified_decision",
        "empty_route",
        "additional_skill",
        "invalid_conditions",
        "missing_evidence",
        "external_evidence",
        "unlisted_evidence",
        "extra_field",
        "missing_finding",
        "unresolved_finding",
        "missing_reviewer_refs",
        "duplicate_exception",
        "missing_digest",
        "invalid_digest_type",
        "wrong_source_key",
    ],
)
def test_invalid_exception_rejected(
    temple, reviewed_temple, case
):
    review = copy.deepcopy(reviewed_temple)
    item = review["verified_bypass_exceptions"][0]

    if case == "unknown_skill":
        item["skill"] = "magic"
    elif case == "incorrect_level":
        item["source_level"] = 50
    elif case == "incorrect_boostability":
        item["source_boostability"] = "yes"
    elif case == "incorrect_line":
        item["source_line"] = 1
    elif case == "incorrect_text":
        item["source_text"] = "Incorrect"
    elif case == "incorrect_revision":
        item["wiki_revision"] = 1
    elif case == "incorrect_quest":
        item["quest_id"] = "another_quest"
    elif case == "unverified_decision":
        item["verification_decision"] = "UNVERIFIED"
    elif case == "empty_route":
        item["alternative_route"] = ""
    elif case == "additional_skill":
        item["alternative_skill_requirements"] = {
            "ranged": 20
        }
    elif case == "invalid_conditions":
        item["non_skill_conditions"].append(None)
    elif case == "missing_evidence":
        item["evidence_refs"] = []
    elif case == "external_evidence":
        item["evidence_refs"] = [
            "https://example.com/unverified"
        ]
    elif case == "unlisted_evidence":
        item["evidence_refs"] = [
            "https://oldschool.runescape.wiki/w/Other_Page"
        ]
    elif case == "extra_field":
        item["unapproved_field"] = True
    elif case == "missing_finding":
        review["review_findings"] = []
    elif case == "unresolved_finding":
        review["review_findings"][0]["status"] = "UNRESOLVED"
    elif case == "missing_reviewer_refs":
        review["reviewer_evidence_refs"] = []
    elif case == "duplicate_exception":
        review["verified_bypass_exceptions"].append(
            copy.deepcopy(item)
        )
    elif case == "missing_digest":
        del item["source_wikitext_sha256"]
    elif case == "invalid_digest_type":
        item["source_wikitext_sha256"] = 123
    elif case == "wrong_source_key":
        item["unsupported_source_field"] = True
    else:
        raise AssertionError("Unknown test case")

    with pytest.raises(VerifiedBypassError):
        effective_skills_with_verified_bypasses(
            temple, review
        )
