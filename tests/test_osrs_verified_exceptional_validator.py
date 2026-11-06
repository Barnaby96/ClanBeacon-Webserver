"""Review-validator tests for three exceptional OSRS quests.

Tests modify temporary review ledgers only. The actual
review ledger, curated definitions, approvals and activation
records remain untouched.
"""

import copy
import importlib.util
import json
from functools import lru_cache
from pathlib import Path

import pytest

from utils.osrs_verified_exceptional_routes import (
    EXCEPTION_SCOPE,
)


TARGETS = (
    "creature_of_fenkenstrain",
    "roving_elves",
    "desert_treasure_i",
)


@lru_cache(maxsize=1)
def originals():
    path = Path(
        "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json"
    )

    records = json.loads(
        path.read_text(encoding="utf-8-sig")
    )["reviews"]

    assert len(records) == 135

    approved = [
        review for review in records
        if (
            review["review_status"] == "APPROVED"
            and review["activation_status"] == "ACTIVATED"
        )
    ]

    pending = [
        review for review in records
        if (
            review["review_status"] == "PENDING"
            and review["activation_status"] == "NOT_ACTIVATED"
        )
    ]

    assert len(approved) == 115

    approved_not_activated = [
        review for review in records
        if (
            review["review_status"] == "APPROVED"
            and review["activation_status"]
            == "NOT_ACTIVATED"
        )
    ]

    assert (
        len(pending),
        len(approved_not_activated),
    ) == (0, 20)

    inactive_ids = {
        review["quest_id"]
        for review in approved_not_activated
    }

    assert len(inactive_ids) == 20
    assert set(TARGETS).issubset(inactive_ids)

    for review in approved_not_activated:
        assert review["approval"]["scope"] == (
            "REQUIREMENTS_REVIEW_ONLY"
        )
        assert review["approval"]["wiki_revision"] == (
            review["wiki_revision"]
        )
        assert "activation" not in review

    assert len(EXCEPTION_SCOPE) == 3
    assert set(EXCEPTION_SCOPE) == set(TARGETS)

    return records


def make_validator():
    path = Path(
        "scripts/validate_osrs_requirement_reviews.py"
    )

    spec = importlib.util.spec_from_file_location(
        "exceptional_validator_regression",
        path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


    # Keep historical review scenarios paired with the original
    # 136-quest catalogue, even after later quest activations.
    plan = json.loads(
        Path("data/osrs_quest_activation_plan_v1.json")
        .read_text(encoding="utf-8")
    )
    excluded_ids = {
        quest_id
        for phase in plan["ordered_phases"][1:]
        for quest_id in phase["quest_ids"]
    }
    assert len(excluded_ids) == 12

    from utils.osrs_quest_data import (
        get_curated_quest_requirements,
    )

    historical_catalogue = tuple(
        quest
        for quest in get_curated_quest_requirements()
        if quest.quest_id not in excluded_ids
    )

    assert len(historical_catalogue) == 136
    assert len({
        quest.quest_id for quest in historical_catalogue
    }) == 136

    # Override only this test-created validator module.
    # The production validator is not modified.
    module.get_curated_quest_requirements = (
        lambda: historical_catalogue
    )

    return module


def make_verified_review(records, quest_id):
    rule = EXCEPTION_SCOPE[quest_id]

    matches = [
        review for review in records
        if review["quest_id"] == quest_id
    ]

    assert len(matches) == 1

    review = matches[0]

    assert review["activation_status"] == "NOT_ACTIVATED"
    assert "activation" not in review

    # Tests exercise the pre-approval validation boundary.
    # After the authorised review approval, temporarily
    # reconstruct a pending review in this copied fixture.
    if review["review_status"] == "APPROVED":
        approval = review.pop("approval")

        assert approval["scope"] == (
            "REQUIREMENTS_REVIEW_ONLY"
        )

        review["review_status"] = "PENDING"
    else:
        assert review["review_status"] == "PENDING"
        assert "approval" not in review

    # Before migration, construct the verified exception
    # from the unresolved finding. After migration, validate
    # and reuse the source-locked documented exception.
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

        findings = [
            finding
            for finding in review["review_findings"]
            if (
                finding["code"] == rule["finding_code"]
                and finding["source_line"] == rule["line"]
                and finding["status"] == "RESOLVED"
            )
        ]

        assert len(findings) == 1
        assert findings[0]["resolution"] == (
            rule["condition_detail"]
        )
        assert findings[0]["resolution_evidence_refs"] == [
            rule["wiki_ref"]
        ]

        return review

    findings = [
        finding
        for finding in review["review_findings"]
        if (
            finding["code"]
            == "SPECIAL_REQUIREMENT_REVIEW"
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

    return review


def make_records(*quest_ids):
    records = copy.deepcopy(originals())

    for quest_id in quest_ids:
        make_verified_review(records, quest_id)

    return records


def validate_temporary_records(tmp_path, records):
    path = tmp_path / "temporary_reviews.json"

    # Preserve the real ledger's complete top-level schema.
    # Only substitute the in-memory review records.
    original_document = json.loads(
        Path(
            "data/osrs_requirement_reviews_v1.json"
        ).read_text(encoding="utf-8-sig")
    )

    assert isinstance(original_document, dict)
    assert "reviews" in original_document
    assert len(original_document["reviews"]) == 135
    assert len(records) == 135

    original_document["reviews"] = records

    path.write_text(
        json.dumps(
            original_document,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    validator = make_validator()
    validator.REVIEWS_PATH = path

    return validator.validate_reviews()


def assert_rejected(tmp_path, records):
    with pytest.raises(ValueError):
        validate_temporary_records(
            tmp_path,
            records,
        )


@pytest.mark.parametrize("quest_id", TARGETS)
def test_valid_exception_is_accepted_while_pending(
    tmp_path, quest_id,
):
    records = make_records(quest_id)

    results = validate_temporary_records(
        tmp_path,
        records,
    )

    assert len(results) == 135
    assert dict(results)[quest_id] == 0

    review = next(
        item for item in records
        if item["quest_id"] == quest_id
    )

    assert review["review_status"] == "PENDING"
    assert review["activation_status"] == "NOT_ACTIVATED"
    assert "approval" not in review
    assert "activation" not in review


def test_all_three_valid_exceptions_pass_together(tmp_path):
    records = make_records(*TARGETS)

    results = validate_temporary_records(
        tmp_path,
        records,
    )

    assert len(results) == 135

    for quest_id in TARGETS:
        assert dict(results)[quest_id] == 0

    assert sum(
        item["review_status"] == "APPROVED"
        and item["activation_status"] == "ACTIVATED"
        for item in records
    ) == 115

    assert sum(
        item["review_status"] == "PENDING"
        and item["activation_status"] == "NOT_ACTIVATED"
        for item in records
    ) == len(TARGETS)

    assert sum(
        item["review_status"] == "APPROVED"
        and item["activation_status"] == "NOT_ACTIVATED"
        for item in records
    ) == 20 - len(TARGETS)


def test_unmodified_baseline_still_validates(tmp_path):
    results = validate_temporary_records(
        tmp_path,
        copy.deepcopy(originals()),
    )

    assert len(results) == 135

    baseline = {
        review["quest_id"]: review
        for review in originals()
    }

    for quest_id in TARGETS:
        review = baseline[quest_id]

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
            assert approval["wiki_revision"] == (
                EXCEPTION_SCOPE[quest_id]["revision"]
            )
            assert (
                "verified_exceptional_requirement"
                in review
            )
        else:
            assert "approval" not in review

        unresolved = sum(
            finding["status"] == "UNRESOLVED"
            for finding in review["review_findings"]
        )

        if "verified_exceptional_requirement" in review:
            assert unresolved == 0
        else:
            assert unresolved == 1

        assert dict(results)[quest_id] == unresolved


@pytest.mark.parametrize("quest_id", TARGETS)
@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("quest_id", "unrelated_quest"),
        ("wiki_revision", -1),
        ("source_line", 999),
        ("source_text", "Incorrect source text"),
        ("source_wikitext_sha256", "0" * 64),
        ("condition_kind", "UNSUPPORTED"),
        ("condition_id", "unsupported_condition"),
        ("verification_decision", "UNVERIFIED"),
        ("authorised_by", "UNAUTHORISED"),
        ("evidence_refs", []),
        (
            "evidence_refs",
            ["https://example.invalid/wiki"],
        ),
    ),
)
def test_invalid_exception_metadata_rejected_before_approval(
    tmp_path, quest_id, field, invalid,
):
    records = make_records(quest_id)

    review = next(
        item for item in records
        if item["quest_id"] == quest_id
    )

    review["verified_exceptional_requirement"][
        field
    ] = invalid

    assert_rejected(tmp_path, records)


@pytest.mark.parametrize("quest_id", TARGETS)
@pytest.mark.parametrize(
    "mutation",
    (
        "missing_key",
        "extra_key",
        "invalid_type",
        "missing_reviewer_evidence",
        "unresolved_independent_verification",
        "unresolved_exception_finding",
        "incorrect_exception_resolution",
        "missing_finding_evidence",
        "duplicate_exception_finding",
        "changed_original_skill",
        "changed_direct_prerequisites",
        "conflicting_bypass",
        "conflicting_conditional_annotations",
    ),
)
def test_invalid_review_evidence_rejected_before_approval(
    tmp_path, quest_id, mutation,
):
    records = make_records(quest_id)
    rule = EXCEPTION_SCOPE[quest_id]

    review = next(
        item for item in records
        if item["quest_id"] == quest_id
    )

    exception = review["verified_exceptional_requirement"]

    if mutation == "missing_key":
        del exception["condition_id"]

    elif mutation == "extra_key":
        exception["unreviewed_override"] = True

    elif mutation == "invalid_type":
        review["verified_exceptional_requirement"] = []

    elif mutation == "missing_reviewer_evidence":
        review["reviewer_evidence_refs"].remove(
            rule["wiki_ref"]
        )

    elif mutation == "unresolved_independent_verification":
        finding = next(
            item
            for item in review["review_findings"]
            if item["code"]
            == "INDEPENDENT_SOURCE_VERIFICATION"
        )

        finding["status"] = "UNRESOLVED"

    elif mutation == "unresolved_exception_finding":
        finding = next(
            item
            for item in review["review_findings"]
            if item["code"] == rule["finding_code"]
        )

        finding["status"] = "UNRESOLVED"

    elif mutation == "incorrect_exception_resolution":
        finding = next(
            item
            for item in review["review_findings"]
            if item["code"] == rule["finding_code"]
        )

        finding["resolution"] = "Unsupported interpretation"

    elif mutation == "missing_finding_evidence":
        finding = next(
            item
            for item in review["review_findings"]
            if item["code"] == rule["finding_code"]
        )

        finding["resolution_evidence_refs"] = []

    elif mutation == "duplicate_exception_finding":
        finding = next(
            item
            for item in review["review_findings"]
            if item["code"] == rule["finding_code"]
        )

        review["review_findings"].append(
            copy.deepcopy(finding)
        )

    elif mutation == "changed_original_skill":
        skill = next(iter(
            review["proposed_direct_skill_requirements"]
        ))

        review["proposed_direct_skill_requirements"][
            skill
        ] += 1

    elif mutation == "changed_direct_prerequisites":
        review[
            "proposed_direct_prerequisite_quest_ids"
        ] = []

    elif mutation == "conflicting_bypass":
        review["verified_bypass_exceptions"] = []

    else:
        review[
            "verified_conditional_skill_annotations"
        ] = []

    assert_rejected(tmp_path, records)


@pytest.mark.parametrize(
    "quest_id",
    TARGETS,
)
def test_missing_resolved_finding_cannot_claim_verification(
    tmp_path, quest_id,
):
    records = make_records(quest_id)
    rule = EXCEPTION_SCOPE[quest_id]

    review = next(
        item for item in records
        if item["quest_id"] == quest_id
    )

    review["review_findings"] = [
        finding
        for finding in review["review_findings"]
        if finding["code"] != rule["finding_code"]
    ]

    assert_rejected(tmp_path, records)


def test_unsupported_quest_cannot_claim_exception(tmp_path):
    records = make_records()

    target = next(
        item
        for item in records
        if item["quest_id"] == "the_lost_tribe"
    )

    rule = EXCEPTION_SCOPE["roving_elves"]

    target["verified_exceptional_requirement"] = {
        "quest_id": target["quest_id"],
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

    assert_rejected(tmp_path, records)


def test_tests_never_change_saved_review_ledger(tmp_path):
    path = Path(
        "data/osrs_requirement_reviews_v1.json"
    )

    before = path.read_bytes()

    records = make_records(*TARGETS)

    validate_temporary_records(
        tmp_path,
        records,
    )

    assert path.read_bytes() == before

    saved = json.loads(
        Path(
            "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json"
        ).read_text(encoding="utf-8-sig")
    )["reviews"]

    for review in saved:
        if review["quest_id"] in TARGETS:
            assert review["review_status"] in (
                "PENDING",
                "APPROVED",
            )
            assert (
                review["activation_status"]
                == "NOT_ACTIVATED"
            )

            if review["review_status"] == "APPROVED":
                assert review["approval"]["scope"] == (
                    "REQUIREMENTS_REVIEW_ONLY"
                )
            else:
                assert "approval" not in review

            assert "activation" not in review

            unresolved = sum(
                finding["status"] == "UNRESOLVED"
                for finding in review["review_findings"]
            )

            if "verified_exceptional_requirement" in review:
                assert unresolved == 0
            else:
                assert unresolved == 1
