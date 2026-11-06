"""Source-locked quest-template exception regression tests.

All approval and activation scenarios are simulated in memory.
No review ledger, curated definitions or database is modified.
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

CASES = {
    "troll_stronghold": (
        15326717,
        1,
        "death_plateau",
    ),
    "horror_from_the_deep": (
        15375082,
        2,
        "miniquest_alfred_grimhands_barcrawl",
    ),
    "icthlarins_little_helper": (
        15365541,
        1,
        "gertrudes_cat",
    ),
}


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
    # Historical template scenarios use the original
    # 136 curated quests and the immutable review snapshot.
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
        "step275_quest_template_validator",
        ROOT / "scripts/validate_osrs_requirement_reviews.py",
    )

    assert spec is not None
    assert spec.loader is not None

    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)

    assert len(proposals["proposals"]) == 214
    assert len(reviews["reviews"]) == 135
    assert len(curated) == 136

    return proposals, reviews, curated, validator


def make_case(baseline, quest_id):
    revision, line_number, prerequisite_id = CASES[quest_id]

    proposal = next(
        item
        for item in baseline[0]["proposals"]
        if item["quest_id"] == quest_id
    )

    review = copy.deepcopy(next(
        item
        for item in baseline[1]["reviews"]
        if item["quest_id"] == quest_id
    ))

    assert proposal["wiki_revision"] == revision
    assert review["wiki_revision"] == revision
    assert review["review_status"] == "APPROVED"
    assert review["activation_status"] == "NOT_ACTIVATED"
    assert "activation" not in review

    # TEST-ONLY: reconstruct the pre-approval boundary
    # within this independent deep-copied review.
    approval = review.pop("approval")
    assert isinstance(approval, dict)
    assert approval["scope"] == "REQUIREMENTS_REVIEW_ONLY"
    assert approval["wiki_revision"] == revision

    review["review_status"] = "PENDING"
    assert "approval" not in review

    source = proposal["requirements_wikitext"]
    line_text = source.splitlines()[line_number - 1]

    assert "{{SCP|Quest}}" in line_text
    assert prerequisite_id in (
        review["proposed_direct_prerequisite_quest_ids"]
    )

    findings = [
        item
        for item in review["review_findings"]
        if item["code"] in (
            "SPECIAL_REQUIREMENT_REVIEW",
            "VERIFIED_QUEST_TEMPLATE_PREREQUISITE",
        )
        and item["source_line"] == line_number
        and item["status"] in ("UNRESOLVED", "RESOLVED")
    ]

    assert len(findings) == 1

    refs = [review["reviewer_evidence_refs"][0]]

    findings[0]["code"] = (
        "VERIFIED_QUEST_TEMPLATE_PREREQUISITE"
    )
    findings[0]["status"] = "RESOLVED"
    findings[0]["resolution"] = (
        "The published Wiki and frozen source confirm this "
        "direct quest prerequisite. The non-numeric template "
        "is not an additional numerical skill requirement."
    )
    findings[0]["resolution_evidence_refs"] = refs

    review["verified_quest_template_exceptions"] = [{
        "quest_id": quest_id,
        "wiki_revision": revision,
        "source_line": line_number,
        "source_text": line_text,
        "source_wikitext_sha256": hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest(),
        "parser_warning_type": "NON_NUMERIC_SCP",
        "prerequisite_quest_id": prerequisite_id,
        "verification_decision": (
            "VERIFIED_DIRECT_QUEST_PREREQUISITE"
        ),
        "evidence_refs": refs,
    }]

    return proposal, review


def recognised(baseline, proposal, review):
    curated_ids = {
        item.quest_id for item in baseline[2]
    }

    return baseline[3].verified_non_numeric_quest_templates(
        proposal,
        review,
        curated_ids,
    )


def activate_in_memory(review):
    result = copy.deepcopy(review)

    for finding in result["review_findings"]:
        if finding["status"] == "UNRESOLVED":
            finding["status"] = "RESOLVED"
            finding["resolution"] = (
                "In-memory regression fixture only."
            )
            finding["resolution_evidence_refs"] = list(
                result["reviewer_evidence_refs"]
            )

    revision = result["wiki_revision"]

    result["review_status"] = "APPROVED"
    result["approval"] = {
        "scope": "REQUIREMENTS_REVIEW_ONLY",
        "wiki_revision": revision,
        "approved_by": "IN_MEMORY_TEST_ONLY",
        "approved_at_utc": "2026-11-01T22:10:00Z",
        "decision_notes": "Synthetic test approval only.",
    }

    result["activation_status"] = "ACTIVATED"
    result["activation"] = {
        "scope": "CURATED_QUEST_RESOLVER_ONLY",
        "wiki_revision": revision,
        "activated_by": "IN_MEMORY_TEST_ONLY",
        "activated_at_utc": "2026-11-01T22:11:00Z",
        "decision_notes": "Synthetic test activation only.",
    }

    return result


def quest_for_review(proposal, review):
    skills = proposal["observations"]["skills"]["skills"]

    return QuestRequirement(
        quest_id=review["quest_id"],
        display_name=proposal["wiki_page_title"],
        direct_skill_requirements=dict(
            review["proposed_direct_skill_requirements"]
        ),
        direct_skill_boostability={
            item["skill"]: item["boostable"]
            for item in skills
        },
        prerequisite_quest_ids=tuple(
            review["proposed_direct_prerequisite_quest_ids"]
        ),
    )


def validate_simulated(
    baseline,
    proposal,
    review,
    extra_warning=None,
):
    proposal_data = copy.deepcopy(baseline[0])
    review_data = copy.deepcopy(baseline[1])
    validator = baseline[3]
    quest_id = review["quest_id"]

    matching_proposals = [
        item for item in proposal_data["proposals"]
        if item["quest_id"] == quest_id
    ]

    assert len(matching_proposals) == 1

    if extra_warning is not None:
        matching_proposals[0]["observations"]["skills"][
            "review_items"
        ].append(copy.deepcopy(extra_warning))

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
    curated.append(quest_for_review(proposal, review))

    def fake_read(path):
        if Path(path) == validator.PROPOSALS_PATH:
            return proposal_data

        if Path(path) == validator.REVIEWS_PATH:
            return review_data

        raise AssertionError(
            f"Unexpected source read: {path}"
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
            return_value=curated,
        ),
    ):
        return validator.validate_reviews()


@pytest.mark.parametrize("quest_id", tuple(CASES))
def test_three_exact_templates_recognised(baseline, quest_id):
    proposal, review = make_case(baseline, quest_id)

    revision, line_number, _ = CASES[quest_id]
    assert proposal["wiki_revision"] == revision

    expected = frozenset({
        (
            "NON_NUMERIC_SCP",
            line_number,
            proposal["requirements_wikitext"].splitlines()[
                line_number - 1
            ],
        )
    })

    assert recognised(baseline, proposal, review) == expected


@pytest.mark.parametrize(
    "quest_id",
    ("horror_from_the_deep", "icthlarins_little_helper"),
)
def test_verified_template_activation_validates_in_memory(
    baseline, quest_id
):
    proposal, review = make_case(baseline, quest_id)
    activated = activate_in_memory(review)

    result = validate_simulated(
        baseline,
        proposal,
        activated,
    )

    assert len(result) == 135
    assert dict(result)[quest_id] == 0


@pytest.mark.parametrize(
    "mutation",
    (
        "wrong_fingerprint",
        "wrong_source_text",
        "wrong_revision",
        "wrong_prerequisite",
        "missing_candidate",
        "missing_evidence",
        "missing_reviewer_evidence",
        "unresolved_finding",
        "wrong_warning_type",
        "duplicate_exception",
        "unexpected_metadata",
    ),
)
def test_malformed_or_unsupported_template_rejected(
    baseline, mutation
):
    proposal, review = make_case(
        baseline,
        "horror_from_the_deep",
    )

    proposal = copy.deepcopy(proposal)
    review = copy.deepcopy(review)
    exception = review[
        "verified_quest_template_exceptions"
    ][0]

    if mutation == "wrong_fingerprint":
        exception["source_wikitext_sha256"] = "0" * 64
    elif mutation == "wrong_source_text":
        exception["source_text"] += " tampered"
    elif mutation == "wrong_revision":
        exception["wiki_revision"] += 1
    elif mutation == "wrong_prerequisite":
        exception["prerequisite_quest_id"] = "death_plateau"
    elif mutation == "missing_candidate":
        proposal["observations"]["prerequisites"][
            "direct_candidates"
        ] = []
    elif mutation == "missing_evidence":
        exception["evidence_refs"] = []
    elif mutation == "missing_reviewer_evidence":
        review["reviewer_evidence_refs"] = []
    elif mutation == "unresolved_finding":
        review["review_findings"][1][
            "status"
        ] = "UNRESOLVED"
    elif mutation == "wrong_warning_type":
        proposal["observations"]["skills"][
            "review_items"
        ][0]["type"] = "UNRECOGNISED_WARNING"
    elif mutation == "duplicate_exception":
        review["verified_quest_template_exceptions"].append(
            copy.deepcopy(exception)
        )
    elif mutation == "unexpected_metadata":
        exception["unapproved_override"] = True
    else:
        raise AssertionError("Unrecognised test mutation")

    with pytest.raises(ValueError):
        recognised(baseline, proposal, review)


def test_no_exception_does_not_suppress_warning(baseline):
    proposal, review = make_case(
        baseline,
        "horror_from_the_deep",
    )

    review.pop("verified_quest_template_exceptions")

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


def test_unrelated_parser_warning_still_blocks_activation(
    baseline,
):
    proposal, review = make_case(
        baseline,
        "horror_from_the_deep",
    )

    unrelated = {
        "type": "UNKNOWN_PARSER_WARNING",
        "line_number": 1,
        "source_text": (
            proposal["requirements_wikitext"].splitlines()[0]
        ),
    }

    with pytest.raises(
        ValueError,
        match="Requirements need further modelling",
    ):
        validate_simulated(
            baseline,
            proposal,
            activate_in_memory(review),
            extra_warning=unrelated,
        )


def test_troll_agility_condition_remains_blocked(baseline):
    proposal, review = make_case(
        baseline,
        "troll_stronghold",
    )

    # Simulate missing conditional verification in memory.
    # The quest-template exception must not waive Agility.
    assert "verified_conditional_skill_annotations" in review
    del review["verified_conditional_skill_annotations"]

    with pytest.raises(
        ValueError,
        match="Requirements need further modelling",
    ):
        validate_simulated(
            baseline,
            proposal,
            activate_in_memory(review),
        )


def test_live_ledger_remains_valid_and_unactivated(baseline):
    result = baseline[3].validate_reviews()

    assert len(result) == 135

    by_id = {
        item["quest_id"]: item
        for item in baseline[1]["reviews"]
    }

    for quest_id in CASES:
        review = by_id[quest_id]

        assert review["review_status"] == "APPROVED"
        assert review["activation_status"] == "NOT_ACTIVATED"
        assert isinstance(review["approval"], dict)
        assert review["approval"]["scope"] == (
            "REQUIREMENTS_REVIEW_ONLY"
        )
        assert review["approval"]["wiki_revision"] == (
            review["wiki_revision"]
        )
        assert "activation" not in review
