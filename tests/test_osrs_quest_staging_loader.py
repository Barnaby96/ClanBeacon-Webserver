"""Regression tests for the explicit OSRS staging-only loader.

All tampering and approval-state changes are simulated in memory.
These tests must not alter the real manifest, reviews or catalogue.
"""

import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import osrs_quest_staging_loader as loader
from utils.osrs_quest_data import get_curated_quest_requirements
from utils.osrs_quest_requirements import (
    build_access_profile_from_quests,
)


EXPECTED_SHA256 = (
    "671a9e93aec27c4bf7f6d8211086f5c"
    "913203da97b677afae52a10e4481a8888"
)

EXPECTED_IDS = (
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

EXPECTED_CONDITIONS = {
    "creature_of_fenkenstrain": (
        "creature_of_fenkenstrain",
        "partial_the_restless_ghost",
    ),
    "desert_treasure_i": (
        "desert_treasure_i",
        "gas_mask_from_plague_city",
    ),
    "elemental_workshop_i": (
        "elemental_workshop_i",
        "assisted_elemental_rock_mining",
    ),
    "roving_elves": (
        "roving_elves",
        "charter_ship_to_elven_woods",
    ),
    "garden_of_tranquillity": (
        "creature_of_fenkenstrain",
        "partial_the_restless_ghost",
    ),
    "mournings_end_part_i": (
        "roving_elves",
        "charter_ship_to_elven_woods",
    ),
}


class _MemoryManifest:
    """Provide manifest bytes without creating or modifying a file."""

    def __init__(self, content):
        self.content = content

    def read_bytes(self):
        return self.content


def _document():
    return json.loads(
        loader._MANIFEST_PATH.read_bytes().decode("utf-8")
    )


def _load_modified(document):
    """Simulate a separately pinned altered manifest in memory.

    Re-pinning is necessary to test semantic validation beyond the
    outer fingerprint guard. The real manifest and loader constants
    are never changed.
    """
    content = (
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")

    fingerprint = hashlib.sha256(content).hexdigest()

    with patch.multiple(
        loader,
        _MANIFEST_PATH=_MemoryManifest(content),
        _MANIFEST_SHA256=fingerprint,
        _MANIFEST_BYTES=len(content),
    ):
        return loader.load_staged_quest_requirements()


def _get_record(document, quest_id):
    return next(
        record
        for record in document["quest_definitions"]
        if record["quest_id"] == quest_id
    )


def _apply_mutation(document, mutation):
    if mutation == "unexpected_manifest_field":
        document["unexpected_field"] = True

    elif mutation == "wrong_schema_version":
        document["schema_version"] = 2

    elif mutation == "production_enabled":
        document["production_catalogue"] = True

    elif mutation == "activation_authorised":
        document["activation_authorised"] = True

    elif mutation == "wrong_purpose":
        document["purpose"] = "LIVE_CURATED_QUEST_CATALOGUE"

    elif mutation == "record_activated":
        document["quest_definitions"][0][
            "activation_status"
        ] = "ACTIVATED"

    elif mutation == "duplicate_quest":
        document["quest_definitions"][-1] = copy.deepcopy(
            document["quest_definitions"][0]
        )

    elif mutation == "unknown_quest":
        document["quest_definitions"][0][
            "quest_id"
        ] = "not_an_approved_quest"

    elif mutation == "unresolved_prerequisite":
        _get_record(
            document, "garden_of_tranquillity"
        )["prerequisite_quest_ids"].append(
            "unknown_prerequisite_quest"
        )

    elif mutation == "mismatched_boostability_keys":
        _get_record(
            document, "between_a_rock"
        )["direct_skill_boostability"].pop("smithing")

    elif mutation == "wrong_revision":
        _get_record(
            document, "recruitment_drive"
        )["wiki_revision"] = -1

    elif mutation == "changed_approved_metadata":
        _get_record(
            document, "creature_of_fenkenstrain"
        )["approved_review_metadata"] = {}

    elif mutation == "missing_condition_field":
        condition = _get_record(
            document, "creature_of_fenkenstrain"
        )["non_skill_conditions"][0]
        condition.pop("condition_id")

    elif mutation == "wrong_condition_association":
        condition = _get_record(
            document, "roving_elves"
        )["non_skill_conditions"][0]
        condition["quest_id"] = "desert_treasure_i"

    elif mutation == "malformed_alternative_route":
        condition = _get_record(
            document, "roving_elves"
        )["non_skill_conditions"][0]
        condition["alternative_skill_route"] = [
            "agility", 56
        ]

    else:
        raise AssertionError(
            f"Unknown test mutation: {mutation}"
        )


def test_pinned_manifest_identity():
    content = loader._MANIFEST_PATH.read_bytes()

    assert len(content) == 18642
    assert hashlib.sha256(content).hexdigest() == EXPECTED_SHA256
    assert loader._MANIFEST_SHA256 == EXPECTED_SHA256
    assert loader._MANIFEST_BYTES == len(content)


def test_manifest_is_explicitly_inactive():
    document = _document()

    assert document["schema_version"] == 1
    assert document["purpose"] == "OFFLINE_CURATED_QUEST_STAGING"
    assert document["production_catalogue"] is False
    assert document["activation_authorised"] is False

    assert all(
        record["activation_status"] == "NOT_ACTIVATED"
        for record in document["quest_definitions"]
    )


def test_all_twelve_definitions_load_in_stable_order():
    quests = loader.load_staged_quest_requirements()

    assert len(quests) == 12
    assert tuple(quest.quest_id for quest in quests) == EXPECTED_IDS


def test_staged_quests_are_not_in_live_catalogue():
    # The staging manifest retains all twelve original
    # definitions, including quests already integrated.
    plan = json.loads(
        (
            loader._ROOT
            / "data/osrs_quest_activation_plan_v1.json"
        ).read_text(encoding="utf-8")
    )

    phases = plan["ordered_phases"]
    assert len(phases) == 3

    phase2_ids = set(phases[1]["quest_ids"])
    phase3_ids = set(phases[2]["quest_ids"])

    assert len(phase2_ids) == 10
    assert len(phase3_ids) == 2
    assert phase2_ids.isdisjoint(phase3_ids)
    assert phase2_ids | phase3_ids == set(EXPECTED_IDS)

    live_before = tuple(get_curated_quest_requirements())
    ids_before = {quest.quest_id for quest in live_before}

    assert len(live_before) == len(ids_before)

    integrated_ids = ids_before.intersection(EXPECTED_IDS)

    # Reject incomplete or out-of-order catalogue changes.
    assert integrated_ids in (
        set(),
        phase2_ids,
        phase2_ids | phase3_ids,
    )

    assert len(live_before) == 136 + len(integrated_ids)

    loaded = loader.load_staged_quest_requirements()

    assert len(loaded) == 12

    staged_by_id = {
        quest.quest_id: quest
        for quest in loaded
    }

    assert len(staged_by_id) == 12
    assert set(staged_by_id) == set(EXPECTED_IDS)

    # An integrated quest must remain identical to its
    # original reviewed staging definition.
    for quest in live_before:
        if quest.quest_id in staged_by_id:
            assert quest == staged_by_id[quest.quest_id]

    live_after = tuple(get_curated_quest_requirements())
    ids_after = {quest.quest_id for quest in live_after}

    # Loading staging data must not change the catalogue.
    assert live_after == live_before
    assert ids_after == ids_before
    assert len(live_after) == 136 + len(integrated_ids)


def test_loader_returns_fresh_definitions():
    first = loader.load_staged_quest_requirements()
    second = loader.load_staged_quest_requirements()

    assert first is not second
    assert first[0] is not second[0]

    original_level = second[0].direct_skill_requirements[
        "smithing"
    ]

    assert original_level == 50

    first[0].direct_skill_requirements["smithing"] = 99

    assert (
        second[0].direct_skill_requirements["smithing"]
        == 50
    )

    third = loader.load_staged_quest_requirements()

    assert third[0].direct_skill_requirements["smithing"] == 50


def test_direct_exceptional_conditions_survive_loading():
    quests = {
        quest.quest_id: quest
        for quest in loader.load_staged_quest_requirements()
    }

    direct_conditions = {
        "creature_of_fenkenstrain",
        "desert_treasure_i",
        "elemental_workshop_i",
        "roving_elves",
    }

    for quest_id, quest in quests.items():
        actual = [
            (condition.quest_id, condition.condition_id)
            for condition in quest.non_skill_conditions
        ]

        expected = EXPECTED_CONDITIONS.get(quest_id)

        if quest_id in direct_conditions:
            assert actual == [expected]
        else:
            assert actual == []


def test_all_quest_profiles_resolve_with_staged_catalogue():
    live = tuple(get_curated_quest_requirements())
    staged = loader.load_staged_quest_requirements()
    live_ids = {quest.quest_id for quest in live}
    assert len(live_ids) == len(live)

    combined = live + tuple(
        quest for quest in staged
        if quest.quest_id not in live_ids
    )

    assert len(combined) == 148
    assert len({quest.quest_id for quest in combined}) == 148

    for quest_id in EXPECTED_IDS:
        profile = build_access_profile_from_quests(
            required_quest_ids=(quest_id,),
            quest_requirements=combined,
        )

        conditions = [
            (condition.quest_id, condition.condition_id)
            for condition in profile.non_skill_conditions
        ]

        expected = EXPECTED_CONDITIONS.get(quest_id)

        assert conditions == (
            [] if expected is None else [expected]
        )


def test_garden_inherits_partial_quest_progression():
    live = tuple(get_curated_quest_requirements())
    live_by_id = {quest.quest_id: quest for quest in live}
    assert len(live_by_id) == len(live)

    staged = loader.load_staged_quest_requirements()
    assert len(staged) == 12
    assert len({quest.quest_id for quest in staged}) == 12

    # Integrated quests must still match their verified
    # original staging definitions.
    for quest in staged:
        if quest.quest_id in live_by_id:
            assert live_by_id[quest.quest_id] == quest

    combined = live + tuple(
        quest for quest in staged
        if quest.quest_id not in live_by_id
    )

    assert len(combined) == 148
    assert len({quest.quest_id for quest in combined}) == 148

    profile = build_access_profile_from_quests(
        required_quest_ids=("garden_of_tranquillity",),
        quest_requirements=combined,
    )

    assert profile.effective_skill_requirements == {
        "crafting": 20,
        "thieving": 25,
        "farming": 25,
    }

    assert profile.skill_boostability_thresholds[
        "farming"
    ]["no"] == 25

    condition = profile.non_skill_conditions[0]

    assert condition.quest_id == "creature_of_fenkenstrain"
    assert condition.condition_kind == "PARTIAL_QUEST_PROGRESSION"
    assert condition.partial_quest_id == "the_restless_ghost"


def test_mourning_inherits_roving_alternative():
    live = tuple(get_curated_quest_requirements())
    live_by_id = {quest.quest_id: quest for quest in live}
    assert len(live_by_id) == len(live)

    staged = loader.load_staged_quest_requirements()
    assert len(staged) == 12
    assert len({quest.quest_id for quest in staged}) == 12

    # Integrated definitions must remain identical to the
    # original verified staging definitions.
    for quest in staged:
        if quest.quest_id in live_by_id:
            assert live_by_id[quest.quest_id] == quest

    combined = live + tuple(
        quest for quest in staged
        if quest.quest_id not in live_by_id
    )

    assert len(combined) == 148
    assert len({quest.quest_id for quest in combined}) == 148

    profile = build_access_profile_from_quests(
        required_quest_ids=("mournings_end_part_i",),
        quest_requirements=combined,
    )

    assert profile.effective_skill_requirements == {
        "ranged": 60,
        "crafting": 10,
        "agility": 56,
        "fletching": 5,
        "cooking": 30,
        "thieving": 50,
    }

    assert profile.skill_boostability_thresholds[
        "ranged"
    ]["no"] == 60

    assert profile.skill_boostability_thresholds[
        "thieving"
    ]["no"] == 50

    condition = profile.non_skill_conditions[0]

    assert condition.quest_id == "roving_elves"
    assert condition.condition_id == "charter_ship_to_elven_woods"
    assert condition.alternative_skill_route == (
        "agility", 56, "yes"
    )


def test_optional_and_assumed_requirements_not_mandatory():
    live = tuple(get_curated_quest_requirements())
    live_by_id = {quest.quest_id: quest for quest in live}
    assert len(live_by_id) == len(live)

    staged = loader.load_staged_quest_requirements()
    assert len(staged) == 12
    assert len({quest.quest_id for quest in staged}) == 12

    # Any integrated quest must retain its original
    # reviewed and verified staging definition.
    for quest in staged:
        if quest.quest_id in live_by_id:
            assert live_by_id[quest.quest_id] == quest

    combined = live + tuple(
        quest for quest in staged
        if quest.quest_id not in live_by_id
    )

    assert len(combined) == 148
    assert len({quest.quest_id for quest in combined}) == 148

    elemental = build_access_profile_from_quests(
        required_quest_ids=("elemental_workshop_i",),
        quest_requirements=combined,
    )

    assert elemental.effective_skill_requirements == {
        "smithing": 20,
        "crafting": 20,
    }

    tai = build_access_profile_from_quests(
        required_quest_ids=("tai_bwo_wannai_trio",),
        quest_requirements=combined,
    )

    assert tai.effective_skill_requirements["fishing"] == 5
    assert "firemaking" not in tai.effective_skill_requirements

    tears = build_access_profile_from_quests(
        required_quest_ids=("tears_of_guthix",),
        quest_requirements=combined,
    )

    assert "quest_points" not in (
        tears.effective_skill_requirements
    )


def test_manifest_byte_tampering_is_rejected():
    original = loader._MANIFEST_PATH.read_bytes()

    changed = bytearray(original)
    changed[-2] = ord(" ")

    assert bytes(changed) != original
    assert len(changed) == len(original)

    with patch.object(
        loader,
        "_MANIFEST_PATH",
        _MemoryManifest(bytes(changed)),
    ):
        with pytest.raises(
            loader.StagingManifestError,
            match="fingerprint",
        ):
            loader.load_staged_quest_requirements()


@pytest.mark.parametrize(
    "mutation",
    (
        "unexpected_manifest_field",
        "wrong_schema_version",
        "production_enabled",
        "activation_authorised",
        "wrong_purpose",
        "record_activated",
        "duplicate_quest",
        "unknown_quest",
        "unresolved_prerequisite",
        "mismatched_boostability_keys",
        "wrong_revision",
        "changed_approved_metadata",
        "missing_condition_field",
        "wrong_condition_association",
        "malformed_alternative_route",
    ),
)
def test_semantically_invalid_manifest_is_rejected(mutation):
    document = _document()
    _apply_mutation(document, mutation)

    with pytest.raises(loader.StagingManifestError):
        _load_modified(document)


def test_source_fingerprint_mismatch_is_rejected():
    def altered_source_hash(path):
        if path == loader._REVIEW_PATH:
            return "0" * 64

        return hashlib.sha256(path.read_bytes()).hexdigest()

    with patch.object(
        loader,
        "_sha256",
        side_effect=altered_source_hash,
    ):
        with pytest.raises(
            loader.StagingManifestError,
            match="provenance",
        ):
            loader.load_staged_quest_requirements()


def test_changed_review_activation_inventory_is_rejected():
    def altered_read_json(path):
        document = json.loads(
            path.read_text(encoding="utf-8-sig")
        )

        if path == loader._REVIEW_PATH:
            activated = next(
                record
                for record in document["reviews"]
                if record["activation_status"] == "ACTIVATED"
            )

            activated["activation_status"] = "NOT_ACTIVATED"

        return document

    with patch.object(
        loader,
        "_read_json",
        side_effect=altered_read_json,
    ):
        with pytest.raises(
            loader.StagingManifestError,
            match="activation inventory",
        ):
            loader.load_staged_quest_requirements()


def test_production_modules_do_not_import_staging_loader():
    root = Path(__file__).resolve().parents[1]

    references = []

    for directory in ("utils", "routes", "cogs"):
        source_root = root / directory

        if not source_root.is_dir():
            continue

        for path in source_root.rglob("*.py"):
            content = path.read_text(
                encoding="utf-8-sig"
            )

            if "osrs_quest_staging_loader" in content:
                references.append(str(path.relative_to(root)))

    assert references == []


# ---------------------------------------------------------------------------
# Historical staging lifecycle: planned activation transition safeguards.
#
# Every transition is simulated in memory. None of these tests changes
# the actual review ledger, curated catalogue, or staging manifest.
# ---------------------------------------------------------------------------

from dataclasses import replace as _phase_replace


_PHASE_LIFECYCLE_CASES = (
    ("current", None),
    ("phase1", None),
    ("phase2", None),
    ("phase3", None),
    (
        "partial_phase1",
        "Current review activation phase",
    ),
    (
        "catalogue_ahead",
        "Current review activation phase",
    ),
    (
        "reviews_ahead",
        "Current review activation phase",
    ),
    (
        "skip_phase1",
        "Current review activation phase",
    ),
    (
        "partial_phase2_catalogue",
        "Unexpected live catalogue inventory",
    ),
    (
        "skip_phase1_at_phase3",
        "Current review activation phase",
    ),
    (
        "changed_staged_requirement",
        "Activated staged definition differs",
    ),
    (
        "missing_exceptional_condition",
        "Activated staged definition differs",
    ),
    (
        "invalid_activation_scope",
        "Invalid current activation record",
    ),
    (
        "missing_activation_metadata",
        "Invalid current activation record",
    ),
    (
        "altered_historical_review_evidence",
        "Historical review evidence changed",
    ),
    (
        "altered_historical_activation",
        "Historical activated review changed",
    ),
)


@pytest.mark.parametrize(
    "scenario, expected_failure",
    _PHASE_LIFECYCLE_CASES,
    ids=[case[0] for case in _PHASE_LIFECYCLE_CASES],
)
def test_phase_aware_lifecycle_scenarios(
    scenario,
    expected_failure,
):
    """Accept only planned states and reject unsafe transitions."""

    plan_path = (
        loader._ROOT / "data/osrs_quest_activation_plan_v1.json"
    )
    current_review_path = (
        loader._ROOT / "data/osrs_requirement_reviews_v1.json"
    )

    plan = json.loads(
        plan_path.read_text(encoding="utf-8")
    )

    # Use the immutable pre-activation baseline, not the evolving
    # live ledger. The mocked reader below still supplies the
    # simulated state to the real staging loader.
    historical_review_path = (
        loader._ROOT
        / "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json"
    )

    assert historical_review_path.resolve() == (
        loader._REVIEW_PATH.resolve()
    )

    document = json.loads(
        historical_review_path.read_text(encoding="utf-8-sig")
    )

    assert plan["execution_authorised"] is False

    phases = plan["ordered_phases"]

    assert len(phases) == 3

    phase1 = set(phases[0]["quest_ids"])
    phase2 = set(phases[1]["quest_ids"])
    phase3 = set(phases[2]["quest_ids"])

    assert (
        len(phase1),
        len(phase2),
        len(phase3),
    ) == (8, 10, 2)

    # Reconstruct the original catalogue so historical
    # lifecycle scenarios remain independent of the actual
    # Phase 2 and Phase 3 activation state.
    current_catalogue = tuple(get_curated_quest_requirements())
    current_ids = {quest.quest_id for quest in current_catalogue}

    assert len(current_catalogue) == len(current_ids)

    integrated_ids = current_ids.intersection(EXPECTED_IDS)

    assert integrated_ids in (
        set(),
        phase2,
        phase2 | phase3,
    )

    assert len(current_catalogue) == 136 + len(integrated_ids)

    live = tuple(
        quest
        for quest in current_catalogue
        if quest.quest_id not in EXPECTED_IDS
    )
    staged = loader.load_staged_quest_requirements()

    assert len(live) == 136
    assert len(staged) == 12

    staged_by_id = {
        quest.quest_id: quest
        for quest in staged
    }

    first_ten = tuple(
        staged_by_id[quest_id]
        for quest_id in phases[1]["quest_ids"]
    )

    catalogue_modes = {
        "live": live,
        "ten": live + first_ten,
        "nine": live + first_ten[:-1],
        "all": live + staged,
    }

    activation_modes = {
        "none": set(),
        "phase1": phase1,
        "partial_phase1": {sorted(phase1)[0]},
        "phase12": phase1 | phase2,
        "phase2_only": phase2,
        "phase23": phase2 | phase3,
        "all": phase1 | phase2 | phase3,
    }

    modes = {
        "current": ("live", "none"),
        "phase1": ("live", "phase1"),
        "phase2": ("ten", "phase12"),
        "phase3": ("all", "all"),
        "partial_phase1": ("live", "partial_phase1"),
        "catalogue_ahead": ("ten", "phase1"),
        "reviews_ahead": ("live", "phase12"),
        "skip_phase1": ("ten", "phase2_only"),
        "partial_phase2_catalogue": ("nine", "phase12"),
        "skip_phase1_at_phase3": ("all", "phase23"),
        "changed_staged_requirement": ("ten", "phase12"),
        "missing_exceptional_condition": ("ten", "phase12"),
        "invalid_activation_scope": ("ten", "phase12"),
        "missing_activation_metadata": ("ten", "phase12"),
        "altered_historical_review_evidence": ("live", "none"),
        "altered_historical_activation": ("live", "none"),
    }

    catalogue_mode, activation_mode = modes[scenario]

    catalogue = catalogue_modes[catalogue_mode]
    activate_ids = activation_modes[activation_mode]

    applied = set()

    for review in document["reviews"]:
        if review["quest_id"] not in activate_ids:
            continue

        assert review["review_status"] == "APPROVED"
        assert review["activation_status"] == "NOT_ACTIVATED"
        assert "activation" not in review

        review["activation_status"] = "ACTIVATED"
        review["activation"] = {
            "scope": "CURATED_QUEST_RESOLVER_ONLY",
            "wiki_revision": review["wiki_revision"],
            "activated_by": "IN_MEMORY_TEST_ONLY",
            "activated_at_utc": "2026-11-03T20:30:00Z",
            "decision_notes": (
                "Regression simulation only. "
                "No real activation."
            ),
        }

        applied.add(review["quest_id"])

    assert applied == activate_ids

    if scenario == "changed_staged_requirement":
        catalogue = tuple(
            _phase_replace(
                quest,
                direct_skill_requirements={
                    **quest.direct_skill_requirements,
                    "smithing": 99,
                },
            )
            if quest.quest_id == "between_a_rock"
            else quest
            for quest in catalogue
        )

    elif scenario == "missing_exceptional_condition":
        catalogue = tuple(
            _phase_replace(
                quest,
                non_skill_conditions=(),
            )
            if quest.quest_id == "elemental_workshop_i"
            else quest
            for quest in catalogue
        )

    elif scenario == "invalid_activation_scope":
        target = next(
            review
            for review in document["reviews"]
            if review["quest_id"] == "elemental_workshop_i"
        )
        target["activation"]["scope"] = "UNAUTHORISED_SCOPE"

    elif scenario == "missing_activation_metadata":
        target = next(
            review
            for review in document["reviews"]
            if review["quest_id"] == "elemental_workshop_i"
        )
        del target["activation"]

    elif scenario == "altered_historical_review_evidence":
        target = next(
            review
            for review in document["reviews"]
            if review["quest_id"] == "between_a_rock"
        )
        target["review_status"] = "PENDING"

    elif scenario == "altered_historical_activation":
        target = next(
            review
            for review in document["reviews"]
            if review["activation_status"] == "ACTIVATED"
        )
        target["activation"]["decision_notes"] += " altered"

    # The real review ledger remains untouched.
    # Only the current-review read is replaced with in-memory data.
    original_read = loader._read_json

    def simulated_read(path):
        if Path(path).resolve() == current_review_path.resolve():
            return copy.deepcopy(document)

        return original_read(path)

    with (
        patch.object(
            loader,
            "_read_json",
            side_effect=simulated_read,
        ),
        patch.object(
            loader,
            "get_curated_quest_requirements",
            return_value=catalogue,
        ),
    ):
        if expected_failure is None:
            actual = loader.load_staged_quest_requirements()

            assert tuple(
                quest.quest_id for quest in actual
            ) == EXPECTED_IDS

        else:
            with pytest.raises(
                loader.StagingManifestError,
                match=expected_failure,
            ):
                loader.load_staged_quest_requirements()
