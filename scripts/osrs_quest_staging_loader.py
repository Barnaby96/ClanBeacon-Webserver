"""Explicit, read-only loader for approved OSRS quest staging data.

This module is intentionally outside the production quest catalogue.
Importing it does not load, expose, approve or activate staged quests.
The manifest is read only when load_staged_quest_requirements() is called.
"""

import hashlib
import json
from dataclasses import fields
from pathlib import Path

from utils.osrs_quest_data import get_curated_quest_requirements
from utils.osrs_quest_requirements import (
    QuestRequirement,
    QuestUnmeasuredCondition,
)

_ROOT = Path(__file__).resolve().parents[1]

_MANIFEST_PATH = _ROOT / "data/osrs_quest_staging_v1.json"
_REVIEW_PATH = _ROOT / "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json"
_PROPOSAL_PATH = _ROOT / "data/osrs_requirement_proposals_v1.json"

_MANIFEST_SHA256 = (
    "671a9e93aec27c4bf7f6d8211086f5c"
    "913203da97b677afae52a10e4481a8888"
)

_MANIFEST_BYTES = 18642

_EXPECTED_IDS = (
    "between_a_rock",
    "creature_of_fenkenstrain",
    "desert_treasure_i",
    "elemental_workshop_i",
    "garden_of_tranquillity",
    "horror_from_the_deep",
    "mournings_end_part_i",
    "recruitment_drive",
    "roving_elves",
    "tai_bwo_wannai_trio",
    "tears_of_guthix",
    "the_lost_tribe",
)

_MANIFEST_FIELDS = {
    "schema_version",
    "purpose",
    "production_catalogue",
    "activation_authorised",
    "source_files_sha256",
    "quest_definitions",
}

_RECORD_FIELDS = {
    "quest_id",
    "display_name",
    "activation_status",
    "wiki_revision",
    "direct_skill_requirements",
    "direct_skill_boostability",
    "prerequisite_quest_ids",
    "non_skill_conditions",
    "approved_review_metadata",
}

_CONDITION_FIELDS = {
    field.name for field in fields(QuestUnmeasuredCondition)
}


class StagingManifestError(ValueError):
    """The staging manifest cannot safely be reconstructed."""


def _require(condition, message):
    if not condition:
        raise StagingManifestError(message)


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_staged_quest_requirements():
    """Return the twelve reviewed, inactive quest definitions.

    This function does not update the live catalogue, review ledger
    or database. The returned objects exist only in the caller's
    memory, and are not activated by loading them.
    """
    raw = _MANIFEST_PATH.read_bytes()

    _require(
        len(raw) == _MANIFEST_BYTES
        and hashlib.sha256(raw).hexdigest() == _MANIFEST_SHA256,
        "Pinned staging manifest fingerprint mismatch",
    )

    manifest = json.loads(raw.decode("utf-8"))

    _require(
        isinstance(manifest, dict)
        and set(manifest) == _MANIFEST_FIELDS,
        "Unexpected staging manifest schema",
    )

    _require(
        manifest["schema_version"] == 1
        and manifest["purpose"] == "OFFLINE_CURATED_QUEST_STAGING"
        and manifest["production_catalogue"] is False
        and manifest["activation_authorised"] is False,
        "Manifest is not restricted to inactive staging",
    )

    source_hashes = {
        str(Path("data/osrs_requirement_reviews_v1.json")):
            _sha256(_REVIEW_PATH),
        str(Path("data/osrs_requirement_proposals_v1.json")):
            _sha256(_PROPOSAL_PATH),
    }

    _require(
        manifest["source_files_sha256"] == source_hashes,
        "Approved source provenance mismatch",
    )

    reviews_document = _read_json(_REVIEW_PATH)
    proposals_document = _read_json(_PROPOSAL_PATH)

    review_records = reviews_document["reviews"]
    proposal_records = proposals_document["proposals"]

    reviews = {
        record["quest_id"]: record
        for record in review_records
    }

    proposals = {
        record["quest_id"]: record
        for record in proposal_records
    }

    _require(
        len(review_records) == len(reviews) == 135
        and len(proposal_records) == len(proposals) == 214,
        "Source review or proposal inventory mismatch",
    )

    _require(
        sum(
            record["activation_status"] == "ACTIVATED"
            for record in review_records
        ) == 115
        and sum(
            record["activation_status"] == "NOT_ACTIVATED"
            for record in review_records
        ) == 20,
        "Actual review activation inventory mismatch",
    )

    live = tuple(get_curated_quest_requirements())
    live_map = {quest.quest_id: quest for quest in live}
    live_ids = set(live_map)

    _require(
        len(live) == len(live_map)
        and len(live) in (136, 146, 148),
        "Unexpected live catalogue inventory",
    )

    records = manifest["quest_definitions"]

    _require(
        isinstance(records, list) and len(records) == 12,
        "Unexpected number of staged definitions",
    )

    expected_ids = set(_EXPECTED_IDS)
    staged = {}

    for record in records:
        _require(
            isinstance(record, dict)
            and set(record) == _RECORD_FIELDS,
            "Unexpected staged quest record schema",
        )

        quest_id = record["quest_id"]

        _require(
            quest_id in expected_ids
            and quest_id not in staged,
            f"Unexpected, duplicate or live staged quest: {quest_id}",
        )

        review = reviews[quest_id]
        proposal = proposals[quest_id]

        expected_metadata = {
            key: value
            for key, value in review.items()
            if (
                key.startswith("verified_")
                or key == "quest_point_assumption"
            )
        }

        _require(
            record["activation_status"] == "NOT_ACTIVATED"
            and review["review_status"] == "APPROVED"
            and review["activation_status"] == "NOT_ACTIVATED"
            and review["approval"]["scope"]
                == "REQUIREMENTS_REVIEW_ONLY"
            and "activation" not in review
            and record["wiki_revision"]
                == review["wiki_revision"]
                == proposal["wiki_revision"]
            and record["display_name"]
                == proposal["wiki_page_title"]
            and record["approved_review_metadata"]
                == expected_metadata,
            f"Approved review mismatch: {quest_id}",
        )

        skills = record["direct_skill_requirements"]
        boostability = record["direct_skill_boostability"]
        prerequisites = record["prerequisite_quest_ids"]
        saved_conditions = record["non_skill_conditions"]

        _require(
            isinstance(skills, dict)
            and isinstance(boostability, dict)
            and set(skills) == set(boostability)
            and isinstance(prerequisites, list)
            and isinstance(saved_conditions, list),
            f"Malformed requirements: {quest_id}",
        )

        conditions = []

        for saved in saved_conditions:
            _require(
                isinstance(saved, dict)
                and set(saved) == _CONDITION_FIELDS
                and saved["quest_id"] == quest_id,
                f"Malformed exceptional condition: {quest_id}",
            )

            values = dict(saved)
            route = values["alternative_skill_route"]

            if route is not None:
                _require(
                    isinstance(route, list) and len(route) == 3,
                    f"Malformed alternative skill route: {quest_id}",
                )
                values["alternative_skill_route"] = tuple(route)

            conditions.append(
                QuestUnmeasuredCondition(**values)
            )

        staged[quest_id] = QuestRequirement(
            quest_id=quest_id,
            display_name=record["display_name"],
            direct_skill_requirements=dict(skills),
            direct_skill_boostability=dict(boostability),
            prerequisite_quest_ids=tuple(prerequisites),
            non_skill_conditions=tuple(conditions),
        )

    _require(
        set(staged) == expected_ids,
        "Incomplete staged quest inventory",
    )

    available_ids = live_ids | expected_ids

    for quest in staged.values():
        _require(
            set(quest.prerequisite_quest_ids) <= available_ids,
            f"Unresolved prerequisite: {quest.quest_id}",
        )

    # The original staging records remain historical evidence.
    # A later activation may place exact copies in the live
    # catalogue, but only in the explicitly planned phases.
    archived_staged_ids = set(staged)

    first_layer = {
        quest_id
        for quest_id, quest in staged.items()
        if set(quest.prerequisite_quest_ids).issubset(
            live_ids - archived_staged_ids
        )
    }

    _require(
        len(first_layer) == 10
        and archived_staged_ids - first_layer
        == {
            "garden_of_tranquillity",
            "mournings_end_part_i",
        },
        "Unexpected historical staging dependency layers",
    )

    exposed = archived_staged_ids & live_ids

    _require(
        exposed in (
            set(),
            first_layer,
            archived_staged_ids,
        )
        and len(live) == 136 + len(exposed),
        "Unexpected staged quest catalogue transition",
    )

    for quest_id in exposed:
        _require(
            live_map[quest_id] == staged[quest_id],
            f"Activated staged definition differs: {quest_id}",
        )

    # Compare the current ledger with the archived reviews.
    # Historical fields must remain identical. Only explicitly
    # phased activation statuses and records may be added.
    current_path = (
        _ROOT / "data/osrs_requirement_reviews_v1.json"
    )

    current_document = _read_json(current_path)
    current_records = current_document["reviews"]

    current_reviews = {
        record["quest_id"]: record
        for record in current_records
    }

    _require(
        len(current_records) == len(current_reviews) == 135
        and set(current_reviews) == set(reviews),
        "Current review inventory differs from historical evidence",
    )

    historical_activated = {
        quest_id
        for quest_id, review in reviews.items()
        if review["activation_status"] == "ACTIVATED"
    }

    original_inactive_live = {
        quest_id
        for quest_id, review in reviews.items()
        if review["activation_status"] == "NOT_ACTIVATED"
        and review["existing_curated_record"] is True
    }

    _require(
        len(historical_activated) == 115
        and len(original_inactive_live) == 8,
        "Historical activation phase baseline mismatch",
    )

    phase_one_active = (
        historical_activated | original_inactive_live
    )

    if not exposed:
        valid_active_sets = (
            historical_activated,
            phase_one_active,
        )
    elif exposed == first_layer:
        valid_active_sets = (
            phase_one_active | first_layer,
        )
    else:
        valid_active_sets = (
            phase_one_active | archived_staged_ids,
        )

    current_activated = {
        quest_id
        for quest_id, review in current_reviews.items()
        if review["activation_status"] == "ACTIVATED"
    }

    _require(
        current_activated in valid_active_sets,
        "Current review activation phase does not match catalogue",
    )

    required_activation_fields = {
        "scope",
        "wiki_revision",
        "activated_by",
        "activated_at_utc",
        "decision_notes",
    }

    for quest_id, historical in reviews.items():
        current = current_reviews[quest_id]

        if quest_id in historical_activated:
            _require(
                current == historical,
                f"Historical activated review changed: {quest_id}",
            )
            continue

        historical_fields = {
            key: value
            for key, value in historical.items()
            if key not in ("activation_status", "activation")
        }

        current_fields = {
            key: value
            for key, value in current.items()
            if key not in ("activation_status", "activation")
        }

        _require(
            current_fields == historical_fields,
            f"Historical review evidence changed: {quest_id}",
        )

        if quest_id in current_activated:
            activation = current.get("activation")

            _require(
                isinstance(activation, dict)
                and set(activation) == required_activation_fields
                and activation["scope"]
                    == "CURATED_QUEST_RESOLVER_ONLY"
                and activation["wiki_revision"]
                    == historical["wiki_revision"]
                and all(
                    isinstance(activation[key], str)
                    and bool(activation[key].strip())
                    for key in (
                        "activated_by",
                        "activated_at_utc",
                        "decision_notes",
                    )
                ),
                f"Invalid current activation record: {quest_id}",
            )
        else:
            _require(
                current["activation_status"] == "NOT_ACTIVATED"
                and "activation" not in current,
                f"Invalid inactive review state: {quest_id}",
            )

    return tuple(staged[quest_id] for quest_id in _EXPECTED_IDS)
