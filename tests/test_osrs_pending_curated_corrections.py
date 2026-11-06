"""In-memory regression scenarios for three pending curated corrections.

These tests neither approve reviews nor modify curated quest data.
Both legacy and corrected definitions are explicitly constructed so
the tests remain valid when the production catalogue is corrected.
"""

from dataclasses import replace

import pytest

from utils.osrs_quest_data import get_curated_quest_requirements
from utils.osrs_quest_requirements import (
    resolve_quest_skill_requirements,
)


LEGACY = {
    "icthlarins_little_helper": ({}, (), {}),
    "in_search_of_the_myreque": (
        {}, ("nature_spirit",), {}
    ),
    "troll_stronghold": ({}, (), {}),
}

CORRECTED = {
    "icthlarins_little_helper": (
        {}, ("gertrudes_cat",), {}
    ),
    "in_search_of_the_myreque": (
        {"agility": 25},
        ("nature_spirit",),
        {"agility": "yes"},
    ),
    "troll_stronghold": (
        {"agility": 15},
        ("death_plateau",),
        {"agility": "yes"},
    ),
}

EXPECTED_AFFECTED = {
    "icthlarins_little_helper",
    "in_search_of_the_myreque",
    "troll_stronghold",
    "beneath_cursed_sands",
    "contact",
    "dragon_slayer_ii",
    "a_night_at_the_theatre",
    "a_taste_of_hope",
    "darkness_of_hallowvale",
    "in_aid_of_the_myreque",
    "sins_of_the_father",
    "the_blood_moon_rises",
    "dream_mentor",
    "eadgars_ruse",
    "troll_romance",
}


@pytest.fixture(scope="module")
def scenarios():
    # Reconstruct the original catalogue for historical
    # Step 278 correction comparisons.
    import json as _json
    from pathlib import Path as _Path

    _plan = _json.loads(
        (
            _Path(__file__).resolve().parents[1]
            / "data/osrs_quest_activation_plan_v1.json"
        ).read_text(encoding="utf-8")
    )

    _later_phase_ids = {
        quest_id
        for phase in _plan["ordered_phases"][1:]
        for quest_id in phase["quest_ids"]
    }

    assert len(_later_phase_ids) == 12

    _full_catalogue = tuple(
        get_curated_quest_requirements()
    )

    assert len({
        quest.quest_id for quest in _full_catalogue
    }) == len(_full_catalogue)

    original = tuple(
        quest
        for quest in _full_catalogue
        if quest.quest_id not in _later_phase_ids
    )
    assert len(original) == 136

    ids = [q.quest_id for q in original]
    assert len(set(ids)) == 136
    assert set(LEGACY) == set(CORRECTED)
    assert set(LEGACY).issubset(ids)

    def variant(overrides):
        result = []

        for quest in original:
            if quest.quest_id not in overrides:
                result.append(quest)
                continue

            skills, prerequisites, boostability = (
                overrides[quest.quest_id]
            )

            result.append(replace(
                quest,
                direct_skill_requirements=dict(skills),
                prerequisite_quest_ids=tuple(prerequisites),
                direct_skill_boostability=dict(boostability),
            ))

        return tuple(result)

    return original, variant(LEGACY), variant(CORRECTED)


def lookup(definitions):
    return {q.quest_id: q for q in definitions}


def resolve(quest_id, definitions):
    return resolve_quest_skill_requirements(
        required_quest_ids=(quest_id,),
        quest_requirements=definitions,
    )


def test_only_three_definitions_differ_between_scenarios(scenarios):
    original, legacy, corrected = scenarios
    before = lookup(legacy)
    after = lookup(corrected)

    changed = {
        quest_id for quest_id in before
        if before[quest_id] != after[quest_id]
    }

    assert changed == set(CORRECTED)
    assert len(original) == len(legacy) == len(corrected) == 136


@pytest.mark.parametrize("quest_id", sorted(CORRECTED))
def test_corrected_direct_requirements(scenarios, quest_id):
    _, _, corrected = scenarios
    quest = lookup(corrected)[quest_id]
    skills, prerequisites, boostability = CORRECTED[quest_id]

    assert quest.direct_skill_requirements == skills
    assert quest.prerequisite_quest_ids == prerequisites
    assert quest.direct_skill_boostability == boostability


@pytest.mark.parametrize("quest_id", (
    "icthlarins_little_helper",
    "contact",
    "beneath_cursed_sands",
    "dragon_slayer_ii",
))
def test_gertrudes_cat_inherited(scenarios, quest_id):
    _, _, corrected = scenarios

    result = resolve(quest_id, corrected)
    assert "gertrudes_cat" in result.quest_ids


@pytest.mark.parametrize("quest_id", (
    "in_search_of_the_myreque",
    "in_aid_of_the_myreque",
    "darkness_of_hallowvale",
    "a_taste_of_hope",
    "sins_of_the_father",
    "a_night_at_the_theatre",
    "the_blood_moon_rises",
))
def test_myreque_agility_inherited_as_boostable(scenarios, quest_id):
    _, _, corrected = scenarios

    result = resolve(quest_id, corrected)

    assert result.effective_skill_requirements["agility"] >= 25
    assert (
        result.skill_boostability_thresholds["agility"]["yes"]
        >= 25
    )


@pytest.mark.parametrize("quest_id", (
    "troll_stronghold",
    "eadgars_ruse",
    "troll_romance",
    "dream_mentor",
    "dragon_slayer_ii",
))
def test_troll_stronghold_requirements_inherited(
    scenarios, quest_id
):
    _, _, corrected = scenarios

    result = resolve(quest_id, corrected)

    assert "death_plateau" in result.quest_ids
    assert result.effective_skill_requirements["agility"] >= 15
    assert (
        result.skill_boostability_thresholds["agility"]["yes"]
        >= 15
    )


def test_a_tail_of_two_cats_is_already_covered(scenarios):
    _, legacy, corrected = scenarios

    before = resolve("a_tail_of_two_cats", legacy)
    after = resolve("a_tail_of_two_cats", corrected)

    assert "gertrudes_cat" in before.quest_ids
    assert before == after


def test_exactly_fifteen_resolver_results_change(scenarios):
    _, legacy, corrected = scenarios

    changed = {
        quest.quest_id
        for quest in legacy
        if (
            resolve(quest.quest_id, legacy)
            != resolve(quest.quest_id, corrected)
        )
    }

    assert changed == EXPECTED_AFFECTED
    assert len(changed) == 15
