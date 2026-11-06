"""Regression tests for bypass-aware review validation."""

import copy
import hashlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.osrs_quest_data import get_curated_quest_requirements
from utils.osrs_quest_requirements import (
    QuestRequirement,
    QuestUnmeasuredCondition,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def baseline():
    proposals = json.loads(
        (ROOT / "data/osrs_requirement_proposals_v1.json")
        .read_text(encoding="utf-8-sig")
    )

    reviews = json.loads(
        (ROOT / "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json")
        .read_text(encoding="utf-8-sig")
    )

    # Bypass regression scenarios must retain the
    # original catalogue alongside historical reviews.
    plan = json.loads(
        (
            ROOT / "data/osrs_quest_activation_plan_v1.json"
        ).read_text(encoding="utf-8")
    )

    phases = plan["ordered_phases"]
    assert len(phases) == 3

    phase2_ids = set(phases[1]["quest_ids"])
    phase3_ids = set(phases[2]["quest_ids"])
    later_ids = phase2_ids | phase3_ids

    assert len(phase2_ids) == 10
    assert len(phase3_ids) == 2
    assert len(later_ids) == 12
    assert "elemental_workshop_i" in phase2_ids

    current = tuple(get_curated_quest_requirements())
    current_ids = {quest.quest_id for quest in current}

    assert len(current_ids) == len(current)

    integrated_ids = current_ids.intersection(later_ids)

    assert integrated_ids in (
        set(),
        phase2_ids,
        later_ids,
    )

    assert len(current) == 136 + len(integrated_ids)

    curated = [
        quest
        for quest in current
        if quest.quest_id not in later_ids
    ]

    assert len(curated) == 136
    assert not any(
        quest.quest_id == "elemental_workshop_i"
        for quest in curated
    )

    spec = importlib.util.spec_from_file_location(
        "clanbeacon_bypass_validator_regression",
        ROOT / "scripts/validate_osrs_requirement_reviews.py",
    )

    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)

    assert len(proposals["proposals"]) == 214
    assert len(reviews["reviews"]) >= 100
    assert all(
        review["review_status"] == "APPROVED"
        and review["activation_status"] == "ACTIVATED"
        for review in reviews["reviews"][:100]
    )
    assert len(curated) >= 129

    return proposals, reviews, curated, validator


def temple_proposal(baseline):
    proposals = baseline[0]["proposals"]

    matches = [
        item for item in proposals
        if item["quest_id"] == "temple_of_ikov"
    ]

    assert len(matches) == 1
    assert matches[0]["wiki_revision"] == 15363124

    return matches[0]


def make_review(baseline):
    proposal = temple_proposal(baseline)
    source = proposal["requirements_wikitext"]

    refs = [
        "https://oldschool.runescape.wiki/w/Temple_of_Ikov",
        (
            "https://oldschool.runescape.wiki/w/"
            "Temple_of_Ikov#Fire_Warrior_of_Lesarkus"
        ),
    ]

    return {
        "quest_id": "temple_of_ikov",
        "wiki_revision": 15363124,
        "review_status": "PENDING",
        "activation_status": "NOT_ACTIVATED",
        "existing_curated_record": False,
        "proposed_direct_skill_requirements": {
            "thieving": 42,
            "ranged": 40,
        },
        "proposed_direct_prerequisite_quest_ids": [],
        "review_findings": [
            {
                "code": "VERIFIED_ACCESSIBLE_BYPASS",
                "source_line": 2,
                "detail": "40 Ranged has an accessible bypass.",
                "status": "RESOLVED",
                "resolution": (
                    "Low-level throwing weapons bypass "
                    "the normal 40 Ranged threshold."
                ),
                "resolution_evidence_refs": refs,
            },
        ],
        "reviewer_evidence_refs": refs,
        "review_notes": (
            "In-memory regression fixture only. "
            "No actual approval or activation."
        ),
        "verified_bypass_exceptions": [
            {
                "quest_id": "temple_of_ikov",
                "skill": "ranged",
                "source_level": 40,
                "source_boostability": "no",
                "source_line": 2,
                "source_text": source.splitlines()[1],
                "source_wikitext_sha256": hashlib.sha256(
                    source.encode("utf-8")
                ).hexdigest(),
                "wiki_revision": 15363124,
                "verification_decision":
                    "VERIFIED_ACCESSIBLE_BYPASS",
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
            },
        ],
    }


def make_approved(review):
    review = copy.deepcopy(review)
    review["review_status"] = "APPROVED"
    review["approval"] = {
        "scope": "REQUIREMENTS_REVIEW_ONLY",
        "wiki_revision": 15363124,
        "approved_by": "IN_MEMORY_TEST_ONLY",
        "approved_at_utc": "2026-11-01T15:00:00Z",
        "decision_notes": "Test fixture; not a real approval.",
    }
    return review


def make_activated(review):
    review = make_approved(review)
    review["activation_status"] = "ACTIVATED"
    review["activation"] = {
        "scope": "CURATED_QUEST_RESOLVER_ONLY",
        "wiki_revision": 15363124,
        "activated_by": "IN_MEMORY_TEST_ONLY",
        "activated_at_utc": "2026-11-01T15:00:00Z",
        "decision_notes": "Test fixture; not a real activation.",
    }
    return review


def make_quest(skills=None, boostability=None):
    return QuestRequirement(
        quest_id="temple_of_ikov",
        display_name="Temple of Ikov",
        direct_skill_requirements=(
            {"thieving": 42} if skills is None else skills
        ),
        direct_skill_boostability=(
            {"thieving": "yes"}
            if boostability is None else boostability
        ),
        prerequisite_quest_ids=(),
    )


def validate_simulated(
    baseline,
    review,
    extra_quest=None,
    proposal_override=None,
):
    proposal_data, review_data, curated, validator = baseline

    simulated_reviews = copy.deepcopy(review_data)
    # Replace any real Temple review only in this
    # in-memory simulation; never modify saved reviews.
    simulated_reviews["reviews"] = [
        item
        for item in simulated_reviews["reviews"]
        if item["quest_id"] != "temple_of_ikov"
    ]
    simulated_reviews["reviews"].append(copy.deepcopy(review))

    effective_proposals = (
        proposal_data
        if proposal_override is None
        else proposal_override
    )

    def fake_read(path):
        if Path(path) == validator.PROPOSALS_PATH:
            return effective_proposals

        if Path(path) == validator.REVIEWS_PATH:
            return simulated_reviews

        raise AssertionError(
            f"Unexpected validator read: {path}"
        )

    simulated_curated = [
        quest
        for quest in curated
        if quest.quest_id != "temple_of_ikov"
    ]

    if extra_quest is not None:
        simulated_curated.append(extra_quest)

    with (
        patch.object(
            validator,
            "read_json",
            side_effect=fake_read,
        ),
        patch.object(
            validator,
            "get_curated_quest_requirements",
            return_value=simulated_curated,
        ),
    ):
        return validator.validate_reviews()


def expected_simulated_count(baseline):
    return 1 + sum(
        review["quest_id"] != "temple_of_ikov"
        for review in baseline[1]["reviews"]
    )


def test_existing_100_activations_unchanged(baseline):
    result = baseline[3].validate_reviews()

    assert len(result) == len(baseline[1]["reviews"])

    unresolved_by_id = dict(result)
    activated = [
        review
        for review in baseline[1]["reviews"]
        if review["review_status"] == "APPROVED"
        and review["activation_status"] == "ACTIVATED"
    ]

    assert len(activated) >= 100
    assert all(
        unresolved_by_id[review["quest_id"]] == 0
        for review in activated
    )


def test_pending_bypass_review_validates(baseline):
    result = validate_simulated(
        baseline, make_review(baseline)
    )
    assert len(result) == expected_simulated_count(baseline)
    assert result[-1] == ("temple_of_ikov", 0)


def test_approved_unactivated_bypass_validates(baseline):
    review = make_approved(make_review(baseline))
    result = validate_simulated(baseline, review)

    assert len(result) == expected_simulated_count(baseline)
    assert result[-1] == ("temple_of_ikov", 0)


def test_bypass_aware_activation_validates(baseline):
    review = make_activated(make_review(baseline))
    result = validate_simulated(
        baseline, review, make_quest()
    )

    assert len(result) == expected_simulated_count(baseline)
    assert result[-1] == ("temple_of_ikov", 0)


def test_strict_ranged_activation_rejected(baseline):
    review = make_activated(make_review(baseline))

    strict = make_quest(
        skills={"thieving": 42, "ranged": 40},
        boostability={"thieving": "yes", "ranged": "no"},
    )

    with pytest.raises(
        ValueError, match="Activated requirements mismatch"
    ):
        validate_simulated(baseline, review, strict)


def test_wrong_effective_boostability_rejected(baseline):
    review = make_activated(make_review(baseline))
    incorrect = make_quest(boostability={"thieving": "no"})

    with pytest.raises(
        ValueError, match="Activated boostability mismatch"
    ):
        validate_simulated(baseline, review, incorrect)


def test_wrong_mandatory_level_rejected(baseline):
    review = make_activated(make_review(baseline))
    incorrect = make_quest(
        skills={"thieving": 41},
        boostability={"thieving": "yes"},
    )

    with pytest.raises(
        ValueError, match="Activated requirements mismatch"
    ):
        validate_simulated(baseline, review, incorrect)


def test_missing_bypass_exception_rejected(baseline):
    review = make_activated(make_review(baseline))
    del review["verified_bypass_exceptions"]

    with pytest.raises(
        ValueError, match="Activated requirements mismatch"
    ):
        validate_simulated(baseline, review, make_quest())


def test_invalid_source_fingerprint_rejected(baseline):
    review = make_activated(make_review(baseline))
    review["verified_bypass_exceptions"][0][
        "source_wikitext_sha256"
    ] = "0" * 64

    with pytest.raises(
        ValueError, match="Invalid verified bypass exception"
    ):
        validate_simulated(baseline, review, make_quest())


def test_invalid_bypass_threshold_rejected(baseline):
    review = make_activated(make_review(baseline))
    review["verified_bypass_exceptions"][0][
        "source_level"
    ] = 50

    with pytest.raises(
        ValueError, match="Invalid verified bypass exception"
    ):
        validate_simulated(baseline, review, make_quest())


def test_unresolved_finding_prevents_approval(baseline):
    review = make_approved(make_review(baseline))
    review["review_findings"][0]["status"] = "UNRESOLVED"

    with pytest.raises(
        ValueError, match="Invalid verified bypass exception"
    ):
        validate_simulated(baseline, review)


def test_other_unresolved_conditional_blocks_activation(baseline):
    review = make_activated(make_review(baseline))

    modified = copy.deepcopy(baseline[0])
    proposal = next(
        item for item in modified["proposals"]
        if item["quest_id"] == "temple_of_ikov"
    )

    extra = copy.deepcopy(
        proposal["observations"]["skills"][
            "conditional_skill_lines"
        ][0]
    )

    extra["line_number"] = 3
    extra["source_text"] = (
        proposal["requirements_wikitext"].splitlines()[2]
    )

    proposal["observations"]["skills"][
        "conditional_skill_lines"
    ].append(extra)

    with pytest.raises(
        ValueError, match="Requirements need further modelling"
    ):
        validate_simulated(
            baseline,
            review,
            make_quest(),
            proposal_override=modified,
        )


def test_unapproved_activation_rejected(baseline):
    review = make_review(baseline)
    review["activation_status"] = "ACTIVATED"
    review["activation"] = {
        "scope": "CURATED_QUEST_RESOLVER_ONLY",
        "wiki_revision": 15363124,
        "activated_by": "IN_MEMORY_TEST_ONLY",
        "activated_at_utc": "2026-11-01T15:00:00Z",
        "decision_notes": "Invalid fixture.",
    }

    with pytest.raises(
        ValueError, match="Unapproved activation"
    ):
        validate_simulated(baseline, review, make_quest())

def make_elemental_condition_case(baseline):
    """Construct a source-backed, in-memory activation candidate."""
    proposal_data, review_data, curated, _ = baseline

    matches = [
        item for item in review_data["reviews"]
        if item["quest_id"] == "elemental_workshop_i"
    ]
    assert len(matches) == 1

    review = matches[0]
    assert review["review_status"] == "APPROVED"
    assert review["activation_status"] == "NOT_ACTIVATED"

    proposals = [
        item for item in proposal_data["proposals"]
        if item["quest_id"] == "elemental_workshop_i"
    ]
    assert len(proposals) == 1

    proposal = proposals[0]
    exceptions = review["verified_bypass_exceptions"]
    assert len(exceptions) == 1

    exception = exceptions[0]
    assert exception["skill"] == "mining"
    assert exception["source_level"] == 20
    assert exception["source_boostability"] == "yes"

    fingerprint = hashlib.sha256(
        proposal["requirements_wikitext"].encode("utf-8")
    ).hexdigest()

    assert exception["source_wikitext_sha256"] == fingerprint

    detail = (
        "20 Mining (boostable), or the verified alternative: "
        + exception["alternative_route"]
        + " Unmeasured conditions: "
        + "; ".join(exception["non_skill_conditions"])
        + "."
    )

    condition = QuestUnmeasuredCondition(
        quest_id="elemental_workshop_i",
        condition_id="assisted_elemental_rock_mining",
        condition_kind="ALTERNATIVE_SKILL_OR_NON_SKILL",
        detail=detail,
        source_wikitext_sha256=fingerprint,
        evidence_status="NOT_INDEPENDENTLY_MEASURED",
        planning_policy="ASSUMED_FOR_PLANNING_ONLY",
        alternative_skill_route=("mining", 20, "yes"),
    )

    quest = QuestRequirement(
        quest_id="elemental_workshop_i",
        display_name=proposal["wiki_page_title"],
        direct_skill_requirements={
            "smithing": 20,
            "crafting": 20,
        },
        direct_skill_boostability={
            "smithing": "yes",
            "crafting": "yes",
        },
        prerequisite_quest_ids=(),
        non_skill_conditions=(condition,),
    )

    assert not any(
        item.quest_id == quest.quest_id
        for item in curated
    )

    return quest, condition


def validate_elemental_condition_case(baseline, quest):
    """Activate Elemental Workshop I only in copied test data."""
    proposal_data, review_data, curated, validator = baseline

    simulated_reviews = copy.deepcopy(review_data)

    matches = [
        item for item in simulated_reviews["reviews"]
        if item["quest_id"] == "elemental_workshop_i"
    ]
    assert len(matches) == 1

    review = matches[0]

    assert review["review_status"] == "APPROVED"
    assert review["activation_status"] == "NOT_ACTIVATED"
    assert "activation" not in review

    review["activation_status"] = "ACTIVATED"
    review["activation"] = {
        "scope": "CURATED_QUEST_RESOLVER_ONLY",
        "wiki_revision": review["wiki_revision"],
        "activated_by": "IN_MEMORY_TEST_ONLY",
        "activated_at_utc": "2026-11-03T18:15:00Z",
        "decision_notes": (
            "Synthetic activation only; no organiser approval."
        ),
    }

    simulated_curated = list(curated) + [quest]

    def fake_read(path):
        if Path(path) == validator.PROPOSALS_PATH:
            return copy.deepcopy(proposal_data)

        if Path(path) == validator.REVIEWS_PATH:
            return copy.deepcopy(simulated_reviews)

        raise AssertionError(
            f"Unexpected validator read: {path}"
        )

    with (
        patch.object(
            validator,
            "read_json",
            side_effect=fake_read,
        ),
        patch.object(
            validator,
            "get_curated_quest_requirements",
            return_value=simulated_curated,
        ),
    ):
        return validator.validate_reviews()


def test_elemental_bypass_condition_valid_activation(baseline):
    quest, _ = make_elemental_condition_case(baseline)

    result = validate_elemental_condition_case(
        baseline, quest
    )

    assert len(result) == 135
    assert dict(result)["elemental_workshop_i"] == 0


def test_elemental_bypass_condition_missing_rejected(baseline):
    quest, _ = make_elemental_condition_case(baseline)

    incorrect = replace(
        quest,
        non_skill_conditions=(),
    )

    with pytest.raises(
        ValueError,
        match="Activated non-skill conditions mismatch",
    ):
        validate_elemental_condition_case(
            baseline, incorrect
        )


def test_elemental_bypass_condition_wrong_level_rejected(baseline):
    quest, condition = make_elemental_condition_case(baseline)

    incorrect = replace(
        quest,
        non_skill_conditions=(
            replace(
                condition,
                alternative_skill_route=("mining", 21, "yes"),
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="Activated non-skill conditions mismatch",
    ):
        validate_elemental_condition_case(
            baseline, incorrect
        )


def test_elemental_bypass_condition_wrong_fingerprint_rejected(
    baseline,
):
    quest, condition = make_elemental_condition_case(baseline)

    incorrect = replace(
        quest,
        non_skill_conditions=(
            replace(
                condition,
                source_wikitext_sha256="0" * 64,
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="Activated non-skill conditions mismatch",
    ):
        validate_elemental_condition_case(
            baseline, incorrect
        )


def test_elemental_bypass_condition_changed_description_rejected(
    baseline,
):
    quest, condition = make_elemental_condition_case(baseline)

    incorrect = replace(
        quest,
        non_skill_conditions=(
            replace(
                condition,
                detail="Unverified Mining waiver.",
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="Activated non-skill conditions mismatch",
    ):
        validate_elemental_condition_case(
            baseline, incorrect
        )


def test_elemental_bypass_condition_extra_condition_rejected(
    baseline,
):
    quest, condition = make_elemental_condition_case(baseline)

    invented = replace(
        condition,
        condition_id="fabricated_extra_route",
    )

    incorrect = replace(
        quest,
        non_skill_conditions=(condition, invented),
    )

    with pytest.raises(
        ValueError,
        match="Activated non-skill conditions mismatch",
    ):
        validate_elemental_condition_case(
            baseline, incorrect
        )


def test_elemental_bypass_condition_temple_of_ikov_preserved(
    baseline,
):
    _, review_document, curated, validator = baseline

    temple_reviews = [
        item for item in review_document["reviews"]
        if item["quest_id"] == "temple_of_ikov"
    ]

    temple_quests = [
        item for item in curated
        if item.quest_id == "temple_of_ikov"
    ]

    assert len(temple_reviews) == 1
    assert len(temple_quests) == 1

    assert temple_reviews[0]["activation_status"] == "ACTIVATED"
    assert temple_quests[0].non_skill_conditions == ()

    result = validator.validate_reviews()

    assert len(result) == 135
    assert dict(result)["temple_of_ikov"] == 0
