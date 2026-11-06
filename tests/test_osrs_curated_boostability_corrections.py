"""Regression protection for Step 278 boostability corrections."""

import json
from dataclasses import replace
from pathlib import Path

from utils.osrs_quest_data import (
    get_curated_quest_requirements,
)
from utils.osrs_quest_requirements import (
    resolve_quest_skill_requirements,
)


EXPECTED = {
    "eadgars_ruse": (
        {"herblore": 31},
        {"druidic_ritual", "troll_stronghold"},
        {"herblore": "yes"},
    ),
    "ghosts_ahoy": (
        {"agility": 25, "cooking": 20},
        {"priest_in_peril", "the_restless_ghost"},
        {"agility": "yes", "cooking": "yes"},
    ),
}

EXPECTED_AFFECTED = {
    "eadgars_ruse",
    "ghosts_ahoy",
    "dream_mentor",
    "dragon_slayer_ii",
}


def catalogue():
    # Historical Step 278 boostability comparisons must
    # retain the original 136-quest catalogue, even after
    # subsequent reviewed quests are integrated.
    plan = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/osrs_quest_activation_plan_v1.json"
        ).read_text(encoding="utf-8")
    )

    later_phase_ids = {
        quest_id
        for phase in plan["ordered_phases"][1:]
        for quest_id in phase["quest_ids"]
    }

    assert len(later_phase_ids) == 12

    full_catalogue = tuple(
        get_curated_quest_requirements()
    )

    assert len({
        quest.quest_id for quest in full_catalogue
    }) == len(full_catalogue)

    quests = tuple(
        quest
        for quest in full_catalogue
        if quest.quest_id not in later_phase_ids
    )

    assert len(quests) == 136
    assert len({q.quest_id for q in quests}) == 136

    return quests


def lookup(quests):
    return {q.quest_id: q for q in quests}


def legacy_catalogue(quests):
    return tuple(
        replace(quest, direct_skill_boostability={})
        if quest.quest_id in EXPECTED
        else quest
        for quest in quests
    )


def resolve(quest_id, quests):
    return resolve_quest_skill_requirements(
        required_quest_ids=(quest_id,),
        quest_requirements=quests,
    )


def test_eadgars_ruse_has_explicit_boostable_herblore():
    quest = lookup(catalogue())["eadgars_ruse"]

    assert dict(quest.direct_skill_requirements) == {
        "herblore": 31,
    }
    assert set(quest.prerequisite_quest_ids) == {
        "druidic_ritual",
        "troll_stronghold",
    }
    assert len(quest.prerequisite_quest_ids) == 2
    assert dict(quest.direct_skill_boostability) == {
        "herblore": "yes",
    }


def test_ghosts_ahoy_has_both_explicit_boostable_skills():
    quest = lookup(catalogue())["ghosts_ahoy"]

    assert dict(quest.direct_skill_requirements) == {
        "agility": 25,
        "cooking": 20,
    }
    assert set(quest.prerequisite_quest_ids) == {
        "priest_in_peril",
        "the_restless_ghost",
    }
    assert len(quest.prerequisite_quest_ids) == 2
    assert dict(quest.direct_skill_boostability) == {
        "agility": "yes",
        "cooking": "yes",
    }


def test_boostability_matches_frozen_source_evidence():
    root = Path(__file__).resolve().parents[1]

    document = json.loads(
        (root / "data/osrs_requirement_proposals_v1.json")
        .read_text(encoding="utf-8-sig")
    )

    proposals = {
        item["quest_id"]: item
        for item in document["proposals"]
    }

    assert len(proposals) == 214

    for quest_id, (skills, _, boostability) in EXPECTED.items():
        entries = (
            proposals[quest_id]["observations"]["skills"]["skills"]
        )

        for skill, level in skills.items():
            matches = [
                entry
                for entry in entries
                if (
                    entry.get("skill") == skill
                    and entry.get("level") == level
                )
            ]

            assert len(matches) == 1

            entry = matches[0]

            assert entry["boostable"].lower() == boostability[skill]
            assert entry["condition_kind"] == "NONE_DETECTED"
            assert entry["needs_condition_review"] is False


def test_corrected_quests_reviews_are_approved_but_inactive():
    root = Path(__file__).resolve().parents[1]

    document = json.loads(
        (root / "data/osrs_requirement_reviews_pre_activation_snapshot_v1.json")
        .read_text(encoding="utf-8-sig")
    )

    reviews = {
        item["quest_id"]: item
        for item in document["reviews"]
    }

    assert len(reviews) == 135

    for quest_id in EXPECTED:
        review = reviews[quest_id]

        assert review["review_status"] == "APPROVED"
        assert review["activation_status"] == "NOT_ACTIVATED"
        assert isinstance(review["approval"], dict)
        assert review["approval"]["scope"] == (
            "REQUIREMENTS_REVIEW_ONLY"
        )
        assert "activation" not in review
        assert all(
            item["status"] == "RESOLVED"
            for item in review["review_findings"]
        )


def test_only_two_definitions_differ_from_legacy_boostability():
    current = catalogue()
    legacy = legacy_catalogue(current)

    current_by_id = lookup(current)
    legacy_by_id = lookup(legacy)

    changed = {
        quest_id
        for quest_id in current_by_id
        if current_by_id[quest_id] != legacy_by_id[quest_id]
    }

    assert changed == set(EXPECTED)

    for quest_id in EXPECTED:
        before = legacy_by_id[quest_id]
        after = current_by_id[quest_id]

        assert dict(before.direct_skill_boostability) == {}
        assert dict(after.direct_skill_boostability) == (
            EXPECTED[quest_id][2]
        )

        assert (
            before.direct_skill_requirements
            == after.direct_skill_requirements
        )
        assert (
            before.prerequisite_quest_ids
            == after.prerequisite_quest_ids
        )
        assert before.access_flags == after.access_flags
        assert (
            before.non_skill_conditions
            == after.non_skill_conditions
        )


def test_exactly_four_quest_resolver_results_change():
    current = catalogue()
    legacy = legacy_catalogue(current)

    affected = set()

    for quest_id in sorted(lookup(current)):
        before = resolve(quest_id, legacy)
        after = resolve(quest_id, current)

        if before == after:
            continue

        affected.add(quest_id)

        assert before.quest_ids == after.quest_ids
        assert (
            before.effective_skill_requirements
            == after.effective_skill_requirements
        )
        assert (
            before.skill_boostability_thresholds
            != after.skill_boostability_thresholds
        )

    assert affected == EXPECTED_AFFECTED


def test_corrected_boostability_is_inherited_correctly():
    current = catalogue()

    eadgar = resolve("eadgars_ruse", current)
    ghosts = resolve("ghosts_ahoy", current)
    dream = resolve("dream_mentor", current)
    dragon = resolve("dragon_slayer_ii", current)

    assert eadgar.skill_boostability_thresholds[
        "herblore"
    ] == {"yes": 31}

    assert ghosts.skill_boostability_thresholds[
        "agility"
    ] == {"yes": 25}

    assert ghosts.skill_boostability_thresholds[
        "cooking"
    ] == {"yes": 20}

    assert dream.skill_boostability_thresholds[
        "herblore"
    ] == {"yes": 31}

    assert dragon.skill_boostability_thresholds[
        "herblore"
    ] == {"yes": 45}

    assert dragon.skill_boostability_thresholds[
        "cooking"
    ] == {"yes": 53}
