"""Activation safeguards for source-locked quest exceptions.

Simulated approvals, activations and curated definitions
exist only within isolated test fixtures.

The actual review ledger and curated quest catalogue
must never be changed by these tests.
"""

import copy
import hashlib
import importlib.util
import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

from utils.osrs_quest_data import (
    get_curated_quest_requirements,
)
from utils.osrs_quest_requirements import (
    QuestUnmeasuredCondition,
)
from utils.osrs_verified_exceptional_routes import (
    effective_verified_exceptional_requirement,
)


TARGETS = (
    "creature_of_fenkenstrain",
    "roving_elves",
    "desert_treasure_i",
)

ALTERNATIVES = (
    "roving_elves",
    "desert_treasure_i",
)


@lru_cache(maxsize=1)
def load_validator_helpers():
    path = Path(
        "tests/test_osrs_verified_exceptional_validator.py"
    )

    spec = importlib.util.spec_from_file_location(
        "step275_37l_validator_helpers",
        path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


@lru_cache(maxsize=1)
def source_documents():
    review_document = json.loads(
        Path(
            "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json"
        ).read_text(encoding="utf-8-sig")
    )

    proposal_document = json.loads(
        Path(
            "data/osrs_requirement_proposals_v1.json"
        ).read_text(encoding="utf-8-sig")
    )

    assert len(review_document["reviews"]) == 135
    assert len(proposal_document["proposals"]) == 214

    proposals = {
        proposal["quest_id"]: proposal
        for proposal in proposal_document["proposals"]
    }

    template_review = next(
        item
        for item in review_document["reviews"]
        if item["quest_id"] == "regicide"
    )

    assert template_review["review_status"] == "APPROVED"
    assert (
        template_review["activation_status"]
        == "ACTIVATED"
    )

    return review_document, proposals, template_review


def make_simulated_review(quest_id):
    helpers = load_validator_helpers()

    review_document, proposals, template = (
        source_documents()
    )

    records = helpers.make_records(quest_id)

    matches = [
        record
        for record in records
        if record["quest_id"] == quest_id
    ]

    assert len(matches) == 1

    review = matches[0]
    rule = helpers.EXCEPTION_SCOPE[quest_id]

    assert review["review_status"] == "PENDING"
    assert (
        review["activation_status"]
        == "NOT_ACTIVATED"
    )
    assert "approval" not in review
    assert "activation" not in review

    # TEST-ONLY: these fields exist solely in a temporary
    # copy of the review document.
    review["review_status"] = "APPROVED"
    review["activation_status"] = "ACTIVATED"

    review["approval"] = copy.deepcopy(
        template["approval"]
    )
    review["activation"] = copy.deepcopy(
        template["activation"]
    )

    review["approval"]["wiki_revision"] = (
        rule["revision"]
    )
    review["activation"]["wiki_revision"] = (
        rule["revision"]
    )

    review["approval"]["decision_notes"] = (
        "TEST-ONLY synthetic approval; "
        "not an organiser decision."
    )
    review["activation"]["decision_notes"] = (
        "TEST-ONLY synthetic activation; "
        "no actual quest activation."
    )

    return records, review


def make_simulated_quest(quest_id, review):
    _, proposals, _ = source_documents()

    effective = (
        effective_verified_exceptional_requirement(
            proposals[quest_id],
            review,
        )
    )

    assert effective is not None

    condition = effective["non_skill_condition"]
    alternative = effective["alternative_skill_route"]

    alternative_tuple = (
        None if alternative is None else (
            alternative["skill"],
            alternative["level"],
            alternative["boostability"],
        )
    )

    unmeasured = QuestUnmeasuredCondition(
        quest_id=quest_id,
        condition_id=condition["condition_id"],
        condition_kind=condition["kind"],
        detail=condition["detail"],
        source_wikitext_sha256=effective[
            "source_wikitext_sha256"
        ],
        evidence_status=condition["evidence_status"],
        planning_policy=condition["planning_policy"],
        partial_quest_id=condition["partial_quest_id"],
        alternative_skill_route=alternative_tuple,
    )

    # Synthetic activation must start with the original
    # 136-quest catalogue, even after later integrations.
    plan = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/osrs_quest_activation_plan_v1.json"
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
    assert set(TARGETS).issubset(phase2_ids)

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
        quest.quest_id == quest_id
        for quest in curated
    )

    template_quest = next(
        quest
        for quest in curated
        if quest.quest_id == "regicide"
    )

    synthetic = replace(
        template_quest,
        quest_id=quest_id,
        display_name=proposals[quest_id][
            "wiki_page_title"
        ],
        direct_skill_requirements=dict(
            effective[
                "effective_direct_skill_requirements"
            ]
        ),
        direct_skill_boostability=dict(
            effective[
                "effective_direct_skill_boostability"
            ]
        ),
        prerequisite_quest_ids=tuple(
            effective["direct_prerequisite_quest_ids"]
        ),
        non_skill_conditions=(unmeasured,),
    )

    return synthetic, unmeasured


def activation_fixture(tmp_path, quest_id):
    helpers = load_validator_helpers()
    review_document, _, _ = source_documents()

    records, review = make_simulated_review(
        quest_id
    )

    candidate, condition = make_simulated_quest(
        quest_id,
        review,
    )

    document = copy.deepcopy(review_document)
    document["reviews"] = records

    temporary_path = (
        tmp_path / f"{quest_id}_reviews.json"
    )

    temporary_path.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    # Reconstruct the original catalogue for historical
    # synthetic activation and validator scenarios.
    plan = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/osrs_quest_activation_plan_v1.json"
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
    assert set(TARGETS).issubset(phase2_ids)

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

    historical = tuple(
        quest
        for quest in current
        if quest.quest_id not in later_ids
    )

    assert len(historical) == 136

    def validate(simulated_candidate):
        # Each invocation receives an independent validator
        # module. Its curated reader is patched in memory only.
        validator = helpers.make_validator()

        validator.REVIEWS_PATH = temporary_path

        validator.get_curated_quest_requirements = (
            lambda: historical + (
                simulated_candidate,
            )
        )

        return validator.validate_reviews()

    return candidate, condition, validate


def assert_condition_mismatch(
    validate, candidate, quest_id,
):
    expected = (
        "Activated non-skill conditions mismatch: "
        + quest_id
    )

    with pytest.raises(ValueError) as failure:
        validate(candidate)

    # Exact error matching proves the activation-specific
    # safeguard rejected the candidate, not some other rule.
    assert str(failure.value) == expected


@pytest.mark.parametrize("quest_id", TARGETS)
def test_correct_synthetic_activation_validates(
    tmp_path, quest_id,
):
    candidate, condition, validate = (
        activation_fixture(tmp_path, quest_id)
    )

    assert candidate.non_skill_conditions == (
        condition,
    )

    results = validate(candidate)

    assert len(results) == 135
    assert dict(results)[quest_id] == 0


@pytest.mark.parametrize("quest_id", TARGETS)
def test_missing_condition_rejected_at_activation(
    tmp_path, quest_id,
):
    candidate, condition, validate = (
        activation_fixture(tmp_path, quest_id)
    )

    # Confirm the correct candidate passes first.
    assert len(validate(candidate)) == 135

    missing = replace(
        candidate,
        non_skill_conditions=(),
    )

    assert_condition_mismatch(
        validate,
        missing,
        quest_id,
    )


@pytest.mark.parametrize("quest_id", TARGETS)
@pytest.mark.parametrize(
    "mutation",
    (
        "detail",
        "condition_id",
        "source_fingerprint",
        "quest_origin",
        "additional_condition",
    ),
)
def test_altered_condition_rejected_at_activation(
    tmp_path, quest_id, mutation,
):
    candidate, condition, validate = (
        activation_fixture(tmp_path, quest_id)
    )

    assert len(validate(candidate)) == 135

    if mutation == "detail":
        modified = replace(
            condition,
            detail=condition.detail + " [altered]",
        )
        conditions = (modified,)

    elif mutation == "condition_id":
        modified = replace(
            condition,
            condition_id="different_valid_condition",
        )
        conditions = (modified,)

    elif mutation == "source_fingerprint":
        modified = replace(
            condition,
            source_wikitext_sha256="0" * 64,
        )
        conditions = (modified,)

    elif mutation == "quest_origin":
        modified = replace(
            condition,
            quest_id="regicide",
        )

        # QuestRequirement rejects a condition associated
        # with the wrong quest during object construction.
        # Such an invalid definition cannot reach the
        # activation validator through its normal API.
        with pytest.raises(
            ValueError,
            match=(
                "Invalid or duplicate quest "
                "non-skill condition"
            ),
        ):
            replace(
                candidate,
                non_skill_conditions=(modified,),
            )

        return

    else:
        extra = replace(
            condition,
            condition_id="additional_valid_condition",
            detail="Undocumented additional condition",
        )

        conditions = (
            condition,
            extra,
        )

    altered = replace(
        candidate,
        non_skill_conditions=conditions,
    )

    assert_condition_mismatch(
        validate,
        altered,
        quest_id,
    )


@pytest.mark.parametrize("quest_id", ALTERNATIVES)
@pytest.mark.parametrize(
    "mutation",
    (
        "required_level",
        "boostability",
    ),
)
def test_alternative_skill_route_must_match_exactly(
    tmp_path, quest_id, mutation,
):
    candidate, condition, validate = (
        activation_fixture(tmp_path, quest_id)
    )

    assert len(validate(candidate)) == 135

    skill, level, boostability = (
        condition.alternative_skill_route
    )

    if mutation == "required_level":
        changed_route = (
            skill,
            level + 1,
            boostability,
        )
    else:
        changed_route = (
            skill,
            level,
            "no" if boostability == "yes" else "yes",
        )

    altered_condition = replace(
        condition,
        alternative_skill_route=changed_route,
    )

    altered_candidate = replace(
        candidate,
        non_skill_conditions=(altered_condition,),
    )

    assert_condition_mismatch(
        validate,
        altered_candidate,
        quest_id,
    )


def test_partial_quest_association_must_match_exactly(
    tmp_path,
):
    quest_id = "creature_of_fenkenstrain"

    candidate, condition, validate = (
        activation_fixture(tmp_path, quest_id)
    )

    assert len(validate(candidate)) == 135

    assert condition.partial_quest_id == (
        "the_restless_ghost"
    )

    altered_condition = replace(
        condition,
        partial_quest_id="priest_in_peril",
    )

    altered_candidate = replace(
        candidate,
        non_skill_conditions=(altered_condition,),
    )

    assert_condition_mismatch(
        validate,
        altered_candidate,
        quest_id,
    )


def test_real_review_and_curated_data_remain_unchanged(
    tmp_path,
):
    review_path = Path(
        "data/osrs_requirement_reviews_v1.json"
    )
    quest_path = Path(
        "utils/osrs_quest_data.py"
    )

    before_review = review_path.read_bytes()
    before_quest = quest_path.read_bytes()

    for quest_id in TARGETS:
        candidate, condition, validate = (
            activation_fixture(tmp_path, quest_id)
        )

        assert len(validate(candidate)) == 135

    assert review_path.read_bytes() == before_review
    assert quest_path.read_bytes() == before_quest

    historical_reviews = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json"
        ).read_text(encoding="utf-8-sig")
    )["reviews"]

    for review in historical_reviews:
        if review["quest_id"] not in TARGETS:
            continue

        assert review["review_status"] in (
            "PENDING",
            "APPROVED",
        )
        assert (
            review["activation_status"]
            == "NOT_ACTIVATED"
        )
        assert "activation" not in review

        if review["review_status"] == "APPROVED":
            approval = review.get("approval")

            assert isinstance(approval, dict)
            assert approval["scope"] == (
                "REQUIREMENTS_REVIEW_ONLY"
            )
            from utils.osrs_verified_exceptional_routes import (
                EXCEPTION_SCOPE,
            )

            assert approval["wiki_revision"] == (
                EXCEPTION_SCOPE[review["quest_id"]]["revision"]
            )
        else:
            assert "approval" not in review

    # Independently check the current or simulated live
    # catalogue and its matching review activation state.
    actual_reviews = json.loads(
        before_review.decode("utf-8-sig")
    )["reviews"]

    actual_by_id = {
        review["quest_id"]: review
        for review in actual_reviews
    }

    assert len(actual_reviews) == len(actual_by_id) == 135

    actual_quests = tuple(
        get_curated_quest_requirements()
    )

    actual_ids = {
        quest.quest_id for quest in actual_quests
    }

    assert len(actual_ids) == len(actual_quests)

    plan = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/osrs_quest_activation_plan_v1.json"
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
    assert set(TARGETS).issubset(phase2_ids)

    integrated_ids = actual_ids.intersection(later_ids)

    assert integrated_ids in (
        set(),
        phase2_ids,
        later_ids,
    )

    assert len(actual_quests) == 136 + len(integrated_ids)
    assert later_ids.issubset(actual_by_id)

    assert sum(
        review["activation_status"] == "ACTIVATED"
        for review in actual_reviews
    ) == 123 + len(integrated_ids)

    assert sum(
        review["activation_status"] == "NOT_ACTIVATED"
        for review in actual_reviews
    ) == 12 - len(integrated_ids)

    # Every later-phase review must agree with whether
    # its quest has actually joined the catalogue.
    for quest_id in later_ids:
        review = actual_by_id[quest_id]
        integrated = quest_id in integrated_ids

        expected_status = (
            "ACTIVATED" if integrated
            else "NOT_ACTIVATED"
        )

        assert review["activation_status"] == expected_status

        if integrated:
            assert review["review_status"] == "APPROVED"

            activation = review.get("activation")
            assert isinstance(activation, dict)

            assert activation["scope"] == (
                "CURATED_QUEST_RESOLVER_ONLY"
            )

            assert activation["wiki_revision"] == (
                review["wiki_revision"]
            )
        else:
            assert "activation" not in review

    # These three historical test targets must follow
    # the exact same activation rules as every other
    # Phase 2 quest.
    for quest_id in TARGETS:
        assert (
            actual_by_id[quest_id]["activation_status"]
            == (
                "ACTIVATED"
                if quest_id in integrated_ids
                else "NOT_ACTIVATED"
            )
        )
