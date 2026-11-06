"""Regression tests for source-locked exceptional quest requirements.

All exceptions are constructed in memory. No review approval,
activation, curated import or player eligibility is performed.
"""

import copy
import json
from functools import lru_cache
from pathlib import Path

import pytest

from utils.osrs_verified_exceptional_routes import (
    EXCEPTION_SCOPE,
    VerifiedExceptionalRouteError,
    effective_verified_exceptional_requirement,
)
from utils.osrs_quest_data import (
    get_curated_quest_requirements,
)
from utils.osrs_quest_requirements import (
    QuestRequirement,
    resolve_quest_skill_requirements,
)


QUEST_IDS = (
    "creature_of_fenkenstrain",
    "roving_elves",
    "desert_treasure_i",
)


@lru_cache(maxsize=1)
def baseline():
    proposal_data = json.loads(
        Path(
            "data/osrs_requirement_proposals_v1.json"
        ).read_text(encoding="utf-8-sig")
    )

    review_data = json.loads(
        Path(
            "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json"
        ).read_text(encoding="utf-8-sig")
    )

    proposals = proposal_data["proposals"]
    reviews = review_data["reviews"]

    assert len(proposals) == 214
    assert len(reviews) == 135

    assert sum(
        review["review_status"] == "APPROVED"
        and review["activation_status"] == "ACTIVATED"
        for review in reviews
    ) == 115

    pending = [
        review for review in reviews
        if review["review_status"] == "PENDING"
        and review["activation_status"] == "NOT_ACTIVATED"
    ]

    approved_inactive = [
        review for review in reviews
        if review["review_status"] == "APPROVED"
        and review["activation_status"] == "NOT_ACTIVATED"
    ]

    assert (
        len(pending),
        len(approved_inactive),
    ) == (0, 20)

    inactive_ids = {
        review["quest_id"]
        for review in approved_inactive
    }

    assert len(inactive_ids) == 20
    assert set(QUEST_IDS).issubset(inactive_ids)

    proposal_revisions = {
        proposal["quest_id"]: proposal["wiki_revision"]
        for proposal in proposals
    }

    for review in approved_inactive:
        approval = review.get("approval")

        assert isinstance(approval, dict)
        assert approval["scope"] == (
            "REQUIREMENTS_REVIEW_ONLY"
        )
        assert approval["wiki_revision"] == (
            proposal_revisions[review["quest_id"]]
        )
        assert "activation" not in review

    return (
        {p["quest_id"]: p for p in proposals},
        {r["quest_id"]: r for r in reviews},
    )


def make_pending_review_fixture(review, quest_id):
    assert review["activation_status"] == "NOT_ACTIVATED"
    assert "activation" not in review

    if review["review_status"] == "APPROVED":
        approval = review.pop("approval")

        assert approval["scope"] == (
            "REQUIREMENTS_REVIEW_ONLY"
        )
        assert approval["wiki_revision"] == (
            EXCEPTION_SCOPE[quest_id]["revision"]
        )

        review["review_status"] = "PENDING"
    else:
        assert review["review_status"] == "PENDING"
        assert "approval" not in review

    return review


def make_case(quest_id):
    proposals, reviews = baseline()

    proposal = copy.deepcopy(proposals[quest_id])
    review = copy.deepcopy(reviews[quest_id])
    rule = EXCEPTION_SCOPE[quest_id]

    review = make_pending_review_fixture(
        review, quest_id
    )

    assert review["review_status"] == "PENDING"
    assert review["activation_status"] == "NOT_ACTIVATED"
    assert "approval" not in review
    assert "activation" not in review

    # Once the permanent review has been documented,
    # reuse its source-locked exceptional requirement.
    # Before migration, retain the original in-memory
    # construction from an unresolved review finding.
    if "verified_exceptional_requirement" in review:
        verified = review["verified_exceptional_requirement"]

        assert verified["quest_id"] == quest_id
        assert verified["wiki_revision"] == rule["revision"]
        assert verified["source_line"] == rule["line"]
        assert verified["source_text"] == rule["source_text"]
        assert verified["source_wikitext_sha256"] == (
            rule["fingerprint"]
        )
        assert verified["condition_kind"] == rule["kind"]
        assert verified["condition_id"] == (
            rule["condition_id"]
        )
        assert verified["verification_decision"] == (
            "VERIFIED_EXCEPTIONAL_QUEST_REQUIREMENT"
        )
        assert verified["authorised_by"] == (
            "CLANBEACON_ORGANISER_STEP_275_32"
        )
        assert verified["evidence_refs"] == [
            rule["wiki_ref"]
        ]

        matching = [
            finding
            for finding in review["review_findings"]
            if (
                finding["code"] == rule["finding_code"]
                and finding["source_line"] == rule["line"]
                and finding["status"] == "RESOLVED"
            )
        ]

        assert len(matching) == 1
        assert matching[0]["resolution"] == (
            rule["condition_detail"]
        )
        assert matching[0]["resolution_evidence_refs"] == [
            rule["wiki_ref"]
        ]

        assert (
            effective_verified_exceptional_requirement(
                proposal, review
            )
            is not None
        )

        return proposal, review

    assert (
        effective_verified_exceptional_requirement(
            proposal, review
        ) is None
    )

    findings = [
        finding
        for finding in review["review_findings"]
        if (
            finding["code"] == "SPECIAL_REQUIREMENT_REVIEW"
            and finding["source_line"] == rule["line"]
            and finding["status"] == "UNRESOLVED"
        )
    ]

    assert len(findings) == 1

    finding = findings[0]

    finding["code"] = rule["finding_code"]
    finding["status"] = "RESOLVED"
    finding["resolution"] = rule["condition_detail"]
    finding["resolution_evidence_refs"] = [
        rule["wiki_ref"]
    ]

    review["verified_exceptional_requirement"] = {
        "quest_id": quest_id,
        "wiki_revision": rule["revision"],
        "source_line": rule["line"],
        "source_text": rule["source_text"],
        "source_wikitext_sha256": rule["fingerprint"],
        "condition_kind": rule["kind"],
        "condition_id": rule["condition_id"],
        "verification_decision": (
            "VERIFIED_EXCEPTIONAL_QUEST_REQUIREMENT"
        ),
        "authorised_by": (
            "CLANBEACON_ORGANISER_STEP_275_32"
        ),
        "evidence_refs": [rule["wiki_ref"]],
    }

    return proposal, review


def check(proposal, review):
    return effective_verified_exceptional_requirement(
        proposal, review
    )


def assert_rejected(proposal, review):
    with pytest.raises(VerifiedExceptionalRouteError):
        check(proposal, review)


def test_exact_three_quest_scope():
    assert set(EXCEPTION_SCOPE) == set(QUEST_IDS)

    assert {
        quest_id: rule["line"]
        for quest_id, rule in EXCEPTION_SCOPE.items()
    } == {
        "creature_of_fenkenstrain": 2,
        "roving_elves": 8,
        "desert_treasure_i": 12,
    }


@pytest.mark.parametrize("quest_id", QUEST_IDS)
def test_unresolved_review_does_not_enable_exception(quest_id):
    proposals, reviews = baseline()

    proposal = copy.deepcopy(proposals[quest_id])
    review = copy.deepcopy(reviews[quest_id])
    rule = EXCEPTION_SCOPE[quest_id]

    review = make_pending_review_fixture(
        review, quest_id
    )

    assert review["review_status"] == "PENDING"
    assert review["activation_status"] == "NOT_ACTIVATED"
    assert "approval" not in review
    assert "activation" not in review

    # After migration, reconstruct the original unresolved
    # state solely in this independent in-memory copy.
    if "verified_exceptional_requirement" in review:
        assert check(proposal, review) is not None

        del review["verified_exceptional_requirement"]

        matching = [
            finding
            for finding in review["review_findings"]
            if (
                finding["code"] == rule["finding_code"]
                and finding["source_line"] == rule["line"]
                and finding["status"] == "RESOLVED"
            )
        ]

        assert len(matching) == 1

        finding = matching[0]
        finding["code"] = "SPECIAL_REQUIREMENT_REVIEW"
        finding["status"] = "UNRESOLVED"
        finding.pop("resolution", None)
        finding.pop("resolution_evidence_refs", None)

    # Without verified exceptional metadata, the helper
    # must never activate an assumed requirement.
    assert check(proposal, review) is None

    unresolved = [
        finding
        for finding in review["review_findings"]
        if finding["status"] == "UNRESOLVED"
    ]

    assert len(unresolved) == 1


@pytest.mark.parametrize("quest_id", QUEST_IDS)
def test_verified_exception_returns_explicit_unmeasured_condition(
    quest_id,
):
    proposal, review = make_case(quest_id)

    result = check(proposal, review)
    rule = EXCEPTION_SCOPE[quest_id]

    assert result["quest_id"] == quest_id

    assert result["direct_prerequisite_quest_ids"] == (
        rule["prerequisites"]
    )

    assert result["source_wikitext_sha256"] == (
        rule["fingerprint"]
    )

    condition = result["non_skill_condition"]

    assert condition == {
        "condition_id": rule["condition_id"],
        "kind": rule["kind"],
        "detail": rule["condition_detail"],
        "evidence_status": "NOT_INDEPENDENTLY_MEASURED",
        "planning_policy": "ASSUMED_FOR_PLANNING_ONLY",
        "partial_quest_id": rule["partial_quest_id"],
    }

    assert "verified_player_ownership" not in result
    assert "player_eligible" not in result
    assert "player_access" not in result


@pytest.mark.parametrize("quest_id", QUEST_IDS)
def test_verification_does_not_mutate_original_inputs(quest_id):
    proposal, review = make_case(quest_id)

    original_proposal = copy.deepcopy(proposal)
    original_review = copy.deepcopy(review)

    result = check(proposal, review)

    assert result is not None
    assert proposal == original_proposal
    assert review == original_review


def test_fenkenstrain_requires_partial_not_full_restless_ghost():
    proposal, review = make_case(
        "creature_of_fenkenstrain"
    )

    result = check(proposal, review)

    assert result["effective_direct_skill_requirements"] == {
        "crafting": 20,
        "thieving": 25,
    }

    assert result["effective_direct_skill_boostability"] == {
        "crafting": "yes",
        "thieving": "yes",
    }

    assert result["direct_prerequisite_quest_ids"] == (
        "priest_in_peril",
    )

    assert (
        "the_restless_ghost"
        not in result["direct_prerequisite_quest_ids"]
    )

    assert result["alternative_skill_route"] is None

    assert result["non_skill_condition"][
        "partial_quest_id"
    ] == "the_restless_ghost"


def test_roving_elves_charter_keeps_original_route_visible():
    proposal, review = make_case("roving_elves")

    result = check(proposal, review)

    assert result["alternative_skill_route"] == {
        "skill": "agility",
        "level": 56,
        "boostability": "yes",
    }

    assert result["effective_direct_skill_requirements"] == {}
    assert result["effective_direct_skill_boostability"] == {}

    assert result["direct_prerequisite_quest_ids"] == (
        "regicide",
        "waterfall_quest",
    )

    assert review[
        "proposed_direct_skill_requirements"
    ]["agility"] == 56


def test_roving_elves_inherited_agility_is_not_removed():
    proposal, review = make_case("roving_elves")

    effective = check(proposal, review)

    temporary_quest = QuestRequirement(
        quest_id="roving_elves",
        display_name="Roving Elves",
        direct_skill_requirements=effective[
            "effective_direct_skill_requirements"
        ],
        direct_skill_boostability=effective[
            "effective_direct_skill_boostability"
        ],
        prerequisite_quest_ids=effective[
            "direct_prerequisite_quest_ids"
        ],
    )

    curated = [
        quest
        for quest in get_curated_quest_requirements()
        if quest.quest_id != "roving_elves"
    ]

    resolved = resolve_quest_skill_requirements(
        ["roving_elves"],
        curated + [temporary_quest],
    )

    assert "regicide" in resolved.quest_ids

    assert resolved.effective_skill_requirements[
        "agility"
    ] == 56

    assert resolved.skill_boostability_thresholds[
        "agility"
    ]["yes"] == 56


def test_desert_treasure_preserves_gas_mask_alternative():
    proposal, review = make_case("desert_treasure_i")

    result = check(proposal, review)

    assert result["alternative_skill_route"] == {
        "skill": "slayer",
        "level": 10,
        "boostability": "no",
    }

    assert result["effective_direct_skill_requirements"] == {
        "thieving": 53,
        "magic": 50,
        "firemaking": 50,
    }

    assert result["effective_direct_skill_boostability"] == {
        "thieving": "no",
        "magic": "no",
        "firemaking": "yes",
    }

    assert "plague_city" not in result[
        "direct_prerequisite_quest_ids"
    ]

    assert result["non_skill_condition"][
        "condition_id"
    ] == "gas_mask_from_plague_city"

    assert result["non_skill_condition"][
        "evidence_status"
    ] == "NOT_INDEPENDENTLY_MEASURED"

    assert review[
        "proposed_direct_skill_requirements"
    ]["slayer"] == 10


@pytest.mark.parametrize("quest_id", QUEST_IDS)
def test_result_does_not_share_mutable_state(quest_id):
    proposal, review = make_case(quest_id)

    first = check(proposal, review)
    second = check(proposal, review)

    assert first == second
    assert first is not second

    first["effective_direct_skill_requirements"].clear()
    first["non_skill_condition"]["condition_id"] = "tampered"

    assert second["non_skill_condition"][
        "condition_id"
    ] == EXCEPTION_SCOPE[quest_id]["condition_id"]

    assert check(proposal, review) == second


@pytest.mark.parametrize("quest_id", QUEST_IDS)
@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("quest_id", "other_quest"),
        ("wiki_revision", -1),
        ("source_line", 999),
        ("source_text", "Modified Wiki source"),
        ("source_wikitext_sha256", "0" * 64),
        ("condition_kind", "UNSUPPORTED"),
        ("condition_id", "unsupported_condition"),
        ("verification_decision", "UNVERIFIED"),
        ("authorised_by", "UNAUTHORISED"),
        ("evidence_refs", []),
        ("evidence_refs", ["https://example.invalid"]),
    ),
)
def test_tampered_exception_fields_rejected(
    quest_id, field, invalid,
):
    proposal, review = make_case(quest_id)

    review["verified_exceptional_requirement"][
        field
    ] = invalid

    assert_rejected(proposal, review)


@pytest.mark.parametrize("quest_id", QUEST_IDS)
@pytest.mark.parametrize(
    "modification",
    (
        "missing_key",
        "extra_key",
        "wrong_metadata_type",
    ),
)
def test_malformed_exception_structure_rejected(
    quest_id, modification,
):
    proposal, review = make_case(quest_id)

    if modification == "missing_key":
        del review[
            "verified_exceptional_requirement"
        ]["condition_id"]

    elif modification == "extra_key":
        review[
            "verified_exceptional_requirement"
        ]["unreviewed_exception"] = True

    else:
        review[
            "verified_exceptional_requirement"
        ] = ["not", "a", "record"]

    assert_rejected(proposal, review)


@pytest.mark.parametrize("quest_id", QUEST_IDS)
@pytest.mark.parametrize(
    "modification",
    (
        "missing_reviewer_reference",
        "unresolved_source_verification",
        "unresolved_exception_finding",
        "incorrect_resolution",
        "missing_finding_evidence",
        "wrong_review_quest",
    ),
)
def test_missing_or_tampered_review_evidence_rejected(
    quest_id, modification,
):
    proposal, review = make_case(quest_id)
    rule = EXCEPTION_SCOPE[quest_id]

    if modification == "missing_reviewer_reference":
        review["reviewer_evidence_refs"].remove(
            rule["wiki_ref"]
        )

    elif modification == "unresolved_source_verification":
        finding = next(
            finding
            for finding in review["review_findings"]
            if finding["code"]
            == "INDEPENDENT_SOURCE_VERIFICATION"
        )

        finding["status"] = "UNRESOLVED"

    elif modification == "unresolved_exception_finding":
        finding = next(
            finding
            for finding in review["review_findings"]
            if finding["code"] == rule["finding_code"]
        )

        finding["status"] = "UNRESOLVED"

    elif modification == "incorrect_resolution":
        finding = next(
            finding
            for finding in review["review_findings"]
            if finding["code"] == rule["finding_code"]
        )

        finding["resolution"] = "Unverified assertion"

    elif modification == "missing_finding_evidence":
        finding = next(
            finding
            for finding in review["review_findings"]
            if finding["code"] == rule["finding_code"]
        )

        finding["resolution_evidence_refs"] = []

    else:
        review["quest_id"] = "wrong_quest"

    assert_rejected(proposal, review)


@pytest.mark.parametrize("quest_id", QUEST_IDS)
@pytest.mark.parametrize(
    "modification",
    (
        "wrong_revision",
        "wrong_source",
        "wrong_original_skill",
        "wrong_prerequisites",
    ),
)
def test_frozen_source_or_original_requirements_rejected(
    quest_id, modification,
):
    proposal, review = make_case(quest_id)

    if modification == "wrong_revision":
        proposal["wiki_revision"] += 1

    elif modification == "wrong_source":
        proposal["requirements_wikitext"] += (
            "\n* Unverified additional condition"
        )

    elif modification == "wrong_original_skill":
        proposal["observations"]["skills"][
            "skills"
        ][0]["level"] += 1

    else:
        review[
            "proposed_direct_prerequisite_quest_ids"
        ] = []

    assert_rejected(proposal, review)


@pytest.mark.parametrize(
    "modification",
    (
        "progression_kind",
        "context_kind",
        "target_quest_ids",
    ),
)
def test_fenkenstrain_partial_progression_tampering_rejected(
    modification,
):
    proposal, review = make_case(
        "creature_of_fenkenstrain"
    )

    progression = proposal["observations"][
        "progression"
    ]["progression_observations"][0]

    if modification == "progression_kind":
        progression["progression_kind"] = "FULL"

    elif modification == "context_kind":
        progression["context_kind"] = "NESTED"

    else:
        progression["target_quest_ids"] = [
            "priest_in_peril"
        ]

    assert_rejected(proposal, review)


@pytest.mark.parametrize(
    "quest_id",
    ("roving_elves", "desert_treasure_i"),
)
@pytest.mark.parametrize(
    "modification",
    (
        "skill_condition_kind",
        "skill_boostability",
        "skill_review_required",
        "line_condition_kind",
        "line_review_required",
    ),
)
def test_alternative_skill_observation_tampering_rejected(
    quest_id, modification,
):
    proposal, review = make_case(quest_id)

    skills = proposal["observations"]["skills"]

    original = next(
        item
        for item in skills["skills"]
        if item["condition_kind"] == "ALTERNATIVE"
    )

    conditional = skills["conditional_skill_lines"][0]

    if modification == "skill_condition_kind":
        original["condition_kind"] = "NONE_DETECTED"

    elif modification == "skill_boostability":
        original["boostable"] = "unknown"

    elif modification == "skill_review_required":
        original["needs_condition_review"] = False

    elif modification == "line_condition_kind":
        conditional["condition_kind"] = "NONE_DETECTED"

    else:
        conditional["needs_review"] = False

    assert_rejected(proposal, review)
