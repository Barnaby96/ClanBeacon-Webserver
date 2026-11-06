"""Regression tests for source-locked conditional skill reviews.

All approval/activation fixtures operate in memory only.
"""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.osrs_quest_data import get_curated_quest_requirements
from utils.osrs_quest_requirements import QuestRequirement


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def baseline():
    proposals = json.loads(
        (
            ROOT / "data/osrs_requirement_proposals_v1.json"
        ).read_text(encoding="utf-8-sig")
    )

    reviews = json.loads(
        (
            ROOT / "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json"
        ).read_text(encoding="utf-8-sig")
    )

    # Historical conditional-skill scenarios use the
    # original 136-quest catalogue alongside the
    # immutable pre-activation review snapshot.
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
        quest for quest in current
        if quest.quest_id not in later_ids
    ]

    spec = importlib.util.spec_from_file_location(
        "step275_conditional_validator",
        ROOT / "scripts/validate_osrs_requirement_reviews.py",
    )

    assert spec is not None
    assert spec.loader is not None

    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)

    assert len(proposals["proposals"]) == 214
    assert len(reviews["reviews"]) == 135
    assert len(curated) == 136

    rules = validator.VERIFIED_CONDITIONAL_SKILL_SCOPE

    assert len(rules) == 4

    return proposals, reviews, curated, validator, rules


def proposal_for(baseline, quest_id):
    matches = [
        item for item in baseline[0]["proposals"]
        if item["quest_id"] == quest_id
    ]
    assert len(matches) == 1
    return copy.deepcopy(matches[0])


def prepare_review(baseline, quest_id):
    matches = [
        item for item in baseline[1]["reviews"]
        if item["quest_id"] == quest_id
    ]
    assert len(matches) == 1

    review = copy.deepcopy(matches[0])
    proposal = proposal_for(baseline, quest_id)

    # The saved review has been approved, but not activated.
    # Reconstruct a pending state only in this deep-copied
    # fixture to preserve pre-approval negative tests.
    assert review["review_status"] == "APPROVED"
    assert review["activation_status"] == "NOT_ACTIVATED"
    assert "activation" not in review

    approval = review.pop("approval")
    assert isinstance(approval, dict)
    assert approval["scope"] == "REQUIREMENTS_REVIEW_ONLY"
    assert approval["wiki_revision"] == proposal["wiki_revision"]

    review["review_status"] = "PENDING"
    assert "approval" not in review

    existing_annotations = review.get(
        "verified_conditional_skill_annotations"
    )

    if existing_annotations is not None:
        assert isinstance(existing_annotations, list)
        expected_annotations = frozenset(
            (skill, line, rule["source_text"])
            for (
                scoped_quest,
                revision,
                line,
                skill,
                level,
                boostability,
                condition_kind,
            ), rule in baseline[4].items()
            if scoped_quest == quest_id
        )
        assert baseline[3].verified_conditional_skill_annotations(
            proposal, review
        ) == expected_annotations

    source = proposal["requirements_wikitext"]
    fingerprint = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()

    exceptions = []

    for scope, rule in baseline[4].items():
        (
            scoped_quest,
            revision,
            line,
            skill,
            level,
            boostability,
            condition_kind,
        ) = scope

        if scoped_quest != quest_id:
            continue

        assert proposal["wiki_revision"] == revision
        assert review["wiki_revision"] == revision
        assert source.splitlines()[line - 1] == rule["source_text"]
        assert rule["wiki_ref"] in review["reviewer_evidence_refs"]

        matching = [
            finding
            for finding in review["review_findings"]
            if finding["source_line"] == line
            and finding["code"] in (
                "SPECIAL_REQUIREMENT_REVIEW",
                "PRACTICAL_OR_OPTIONAL_CONDITION_REVIEW",
                "VERIFIED_CONDITIONAL_SKILL_ANNOTATION",
            )
        ]

        assert len(matching) == 1

        finding = matching[0]
        finding["code"] = (
            "VERIFIED_CONDITIONAL_SKILL_ANNOTATION"
        )
        finding["status"] = "RESOLVED"
        finding["resolution"] = rule["verified_interpretation"]
        finding["resolution_evidence_refs"] = [rule["wiki_ref"]]

        exceptions.append({
            "quest_id": quest_id,
            "wiki_revision": revision,
            "source_line": line,
            "source_text": rule["source_text"],
            "source_wikitext_sha256": fingerprint,
            "skill": skill,
            "source_level": level,
            "source_boostability": boostability,
            "condition_kind": condition_kind,
            "annotation_kind": rule["annotation_kind"],
            "verified_interpretation": (
                rule["verified_interpretation"]
            ),
            "verification_decision": (
                "VERIFIED_CONDITIONAL_SKILL_ANNOTATION"
            ),
            "evidence_refs": [rule["wiki_ref"]],
        })

    assert exceptions

    review["verified_conditional_skill_annotations"] = exceptions

    return proposal, review


def recognised(baseline, proposal, review):
    return baseline[3].verified_conditional_skill_annotations(
        proposal, review
    )


def targeted_exception(review, scope):
    matches = [
        item
        for item in review[
            "verified_conditional_skill_annotations"
        ]
        if item["source_line"] == scope[2]
        and item["skill"] == scope[3]
    ]

    assert len(matches) == 1
    return matches[0]


def activate_in_memory(review):
    result = copy.deepcopy(review)

    assert all(
        finding["status"] == "RESOLVED"
        for finding in result["review_findings"]
    )

    revision = result["wiki_revision"]

    result["review_status"] = "APPROVED"
    result["approval"] = {
        "scope": "REQUIREMENTS_REVIEW_ONLY",
        "wiki_revision": revision,
        "approved_by": "IN_MEMORY_TEST_ONLY",
        "approved_at_utc": "2026-11-02T11:00:00Z",
        "decision_notes": (
            "Synthetic regression test; no real approval."
        ),
    }

    result["activation_status"] = "ACTIVATED"
    result["activation"] = {
        "scope": "CURATED_QUEST_RESOLVER_ONLY",
        "wiki_revision": revision,
        "activated_by": "IN_MEMORY_TEST_ONLY",
        "activated_at_utc": "2026-11-02T12:00:00Z",
        "decision_notes": (
            "Synthetic regression test; no real activation."
        ),
    }

    return result


def make_quest(proposal, review, boostability_override=None):
    direct_boostability = {
        item["skill"]: item["boostable"]
        for item in proposal["observations"]["skills"]["skills"]
    }

    if boostability_override is not None:
        direct_boostability.update(boostability_override)

    return QuestRequirement(
        quest_id=review["quest_id"],
        display_name=proposal["wiki_page_title"],
        direct_skill_requirements=dict(
            review["proposed_direct_skill_requirements"]
        ),
        direct_skill_boostability=direct_boostability,
        prerequisite_quest_ids=tuple(
            review["proposed_direct_prerequisite_quest_ids"]
        ),
    )


def validate_simulated(
    baseline,
    proposal,
    review,
    extra_condition=None,
    boostability_override=None,
):
    validator = baseline[3]
    quest_id = review["quest_id"]

    proposal_data = copy.deepcopy(baseline[0])
    review_data = copy.deepcopy(baseline[1])

    matches = [
        item
        for item in proposal_data["proposals"]
        if item["quest_id"] == quest_id
    ]

    assert len(matches) == 1

    effective_proposal = copy.deepcopy(proposal)

    if extra_condition is not None:
        effective_proposal["observations"]["skills"][
            "conditional_skill_lines"
        ].append(copy.deepcopy(extra_condition))

    index = proposal_data["proposals"].index(matches[0])
    proposal_data["proposals"][index] = effective_proposal

    review_data["reviews"] = [
        item
        for item in review_data["reviews"]
        if item["quest_id"] != quest_id
    ]
    review_data["reviews"].append(copy.deepcopy(review))

    curated = [
        item
        for item in baseline[2]
        if item.quest_id != quest_id
    ]

    curated.append(
        make_quest(
            proposal,
            review,
            boostability_override=boostability_override,
        )
    )

    def fake_read(path):
        if Path(path) == validator.PROPOSALS_PATH:
            return proposal_data

        if Path(path) == validator.REVIEWS_PATH:
            return review_data

        raise AssertionError(f"Unexpected read: {path}")

    with (
        patch.object(
            validator,
            "read_json",
            side_effect=fake_read,
        ),
        patch.object(
            validator,
            "get_curated_quest_requirements",
            return_value=curated,
        ),
    ):
        return validator.validate_reviews()


@pytest.mark.parametrize("scope_index", range(4))
def test_exact_annotations_recognised(baseline, scope_index):
    scope = list(baseline[4])[scope_index]
    proposal, review = prepare_review(baseline, scope[0])

    recognised_items = recognised(baseline, proposal, review)

    assert (
        scope[3],
        scope[2],
        baseline[4][scope]["source_text"],
    ) in recognised_items

    assert len(recognised_items) == sum(
        key[0] == scope[0]
        for key in baseline[4]
    )


@pytest.mark.parametrize("scope_index", range(4))
@pytest.mark.parametrize(
    "mutation",
    (
        "wrong_hash",
        "wrong_source_text",
        "wrong_revision",
        "wrong_level",
        "wrong_boostability",
        "wrong_interpretation",
        "missing_evidence",
        "unexpected_metadata",
    ),
)
def test_invalid_exception_metadata_rejected(
    baseline, scope_index, mutation
):
    scope = list(baseline[4])[scope_index]
    proposal, review = prepare_review(baseline, scope[0])
    exception = targeted_exception(review, scope)

    if mutation == "wrong_hash":
        exception["source_wikitext_sha256"] = "0" * 64
    elif mutation == "wrong_source_text":
        exception["source_text"] += " altered"
    elif mutation == "wrong_revision":
        exception["wiki_revision"] += 1
    elif mutation == "wrong_level":
        exception["source_level"] += 1
    elif mutation == "wrong_boostability":
        exception["source_boostability"] = (
            "no"
            if exception["source_boostability"] == "yes"
            else "yes"
        )
    elif mutation == "wrong_interpretation":
        exception["verified_interpretation"] = (
            "All restrictions waived"
        )
    elif mutation == "missing_evidence":
        exception["evidence_refs"] = []
    elif mutation == "unexpected_metadata":
        exception["unapproved_override"] = True
    else:
        raise AssertionError("Unknown mutation")

    with pytest.raises(ValueError):
        recognised(baseline, proposal, review)


@pytest.mark.parametrize("scope_index", range(4))
@pytest.mark.parametrize(
    "mutation",
    (
        "unresolved_finding",
        "missing_finding",
        "altered_skill_observation",
        "duplicate_exception",
    ),
)
def test_broken_review_linkage_rejected(
    baseline, scope_index, mutation
):
    scope = list(baseline[4])[scope_index]
    proposal, review = prepare_review(baseline, scope[0])
    exception = targeted_exception(review, scope)

    if mutation in (
        "unresolved_finding",
        "missing_finding",
    ):
        matching = [
            finding
            for finding in review["review_findings"]
            if finding["source_line"] == scope[2]
            and finding["code"]
            == "VERIFIED_CONDITIONAL_SKILL_ANNOTATION"
        ]

        assert len(matching) == 1

        if mutation == "unresolved_finding":
            matching[0]["status"] = "UNRESOLVED"
        else:
            review["review_findings"].remove(matching[0])

    elif mutation == "altered_skill_observation":
        matches = [
            item
            for item in proposal["observations"]["skills"][
                "skills"
            ]
            if item["skill"] == scope[3]
            and item["line_number"] == scope[2]
        ]

        assert len(matches) == 1
        matches[0]["level"] += 1

    elif mutation == "duplicate_exception":
        review[
            "verified_conditional_skill_annotations"
        ].append(copy.deepcopy(exception))

    else:
        raise AssertionError("Unknown mutation")

    with pytest.raises(ValueError):
        recognised(baseline, proposal, review)


@pytest.mark.parametrize(
    "quest_id",
    ("troll_stronghold", "tears_of_guthix"),
)
def test_annotated_activation_validates_in_memory(
    baseline, quest_id
):
    proposal, review = prepare_review(baseline, quest_id)

    result = validate_simulated(
        baseline,
        proposal,
        activate_in_memory(review),
    )

    assert len(result) == 135
    assert dict(result)[quest_id] == 0


def test_missing_annotation_still_blocks_activation(baseline):
    proposal, review = prepare_review(
        baseline, "tears_of_guthix"
    )

    review.pop(
        "verified_conditional_skill_annotations"
    )

    assert recognised(
        baseline, proposal, review
    ) == frozenset()

    with pytest.raises(
        ValueError,
        match="Requirements need further modelling",
    ):
        validate_simulated(
            baseline,
            proposal,
            activate_in_memory(review),
        )


def test_unrelated_conditional_line_still_blocks(baseline):
    proposal, review = prepare_review(
        baseline, "tears_of_guthix"
    )

    extra = copy.deepcopy(
        proposal["observations"]["skills"][
            "conditional_skill_lines"
        ][0]
    )

    extra["line_number"] = 2
    extra["source_text"] = (
        proposal["requirements_wikitext"].splitlines()[1]
    )

    with pytest.raises(
        ValueError,
        match="Requirements need further modelling",
    ):
        validate_simulated(
            baseline,
            proposal,
            activate_in_memory(review),
            extra_condition=extra,
        )


def test_wrong_curated_boostability_still_blocks(baseline):
    proposal, review = prepare_review(
        baseline, "tears_of_guthix"
    )

    with pytest.raises(
        ValueError,
        match="Activated boostability mismatch",
    ):
        validate_simulated(
            baseline,
            proposal,
            activate_in_memory(review),
            boostability_override={"crafting": "no"},
        )


def test_live_ledger_unchanged_and_valid(baseline):
    result = baseline[3].validate_reviews()

    assert len(result) == 135

    reviews = baseline[1]["reviews"]

    assert sum(
        r["review_status"] == "APPROVED"
        and r["activation_status"] == "ACTIVATED"
        for r in reviews
    ) == 115

    pending = [
        r for r in reviews
        if r["review_status"] == "PENDING"
        and r["activation_status"] == "NOT_ACTIVATED"
    ]

    approved_inactive = [
        r for r in reviews
        if r["review_status"] == "APPROVED"
        and r["activation_status"] == "NOT_ACTIVATED"
    ]

    assert (
        len(pending),
        len(approved_inactive),
    ) == (0, 20)

    expected_revisions = {
        "creature_of_fenkenstrain": 15343497,
        "roving_elves": 15374498,
        "desert_treasure_i": 15374595,
    }

    proposal_revisions = {
        item["quest_id"]: item["wiki_revision"]
        for item in baseline[0]["proposals"]
    }

    assert set(expected_revisions).issubset({
        r["quest_id"] for r in approved_inactive
    })

    for review in approved_inactive:
        approval = review.get("approval")

        assert isinstance(approval, dict)
        assert approval["scope"] == (
            "REQUIREMENTS_REVIEW_ONLY"
        )
        assert approval["wiki_revision"] == (
            proposal_revisions[review["quest_id"]]
        )

        if review["quest_id"] in expected_revisions:
            assert approval["wiki_revision"] == (
                expected_revisions[review["quest_id"]]
            )

        assert "activation" not in review

    for quest_id in (
        "tai_bwo_wannai_trio",
        "troll_stronghold",
        "tears_of_guthix",
    ):
        matches = [
            r for r in reviews
            if r["quest_id"] == quest_id
        ]

        assert len(matches) == 1
        assert matches[0]["review_status"] == "APPROVED"
        assert matches[0]["activation_status"] == "NOT_ACTIVATED"
        assert matches[0]["approval"]["scope"] == (
            "REQUIREMENTS_REVIEW_ONLY"
        )
        assert matches[0]["approval"]["wiki_revision"] == (
            proposal_revisions[quest_id]
        )
        assert "activation" not in matches[0]
