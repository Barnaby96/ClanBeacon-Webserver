"""Regression coverage for unmeasured OSRS quest requirements.

These tests use synthetic quest definitions and do not
approve, activate or import any quest requirements.
"""

import pytest

from utils.board_generation import AccessProfile
from utils.osrs_player_access import assess_player_source_access
from utils.osrs_quest_requirements import (
    QuestRequirement,
    QuestUnmeasuredCondition,
    build_access_profile_from_quests,
    resolve_quest_skill_requirements,
)


def partial_condition(quest_id="test_ancestor"):
    return QuestUnmeasuredCondition(
        quest_id=quest_id,
        condition_id="partial_the_restless_ghost",
        condition_kind="PARTIAL_QUEST_PROGRESSION",
        detail="Partial progress through The Restless Ghost",
        source_wikitext_sha256="a" * 64,
        partial_quest_id="the_restless_ghost",
    )


def mask_condition(quest_id="test_destination"):
    return QuestUnmeasuredCondition(
        quest_id=quest_id,
        condition_id="gas_mask_from_plague_city",
        condition_kind="ALTERNATIVE_SKILL_OR_NON_SKILL",
        detail="Gas mask alternative to unboostable Slayer",
        source_wikitext_sha256="b" * 64,
        alternative_skill_route=("slayer", 10, "no"),
    )


def quest_chain():
    ancestor = QuestRequirement(
        quest_id="test_ancestor",
        display_name="Test Ancestor",
        direct_skill_requirements={"magic": 50},
        direct_skill_boostability={"magic": "no"},
        non_skill_conditions=(partial_condition(),),
    )

    intermediate = QuestRequirement(
        quest_id="test_intermediate",
        display_name="Test Intermediate",
        direct_skill_requirements={"crafting": 20},
        direct_skill_boostability={"crafting": "yes"},
        prerequisite_quest_ids=("test_ancestor",),
    )

    destination = QuestRequirement(
        quest_id="test_destination",
        display_name="Test Destination",
        direct_skill_requirements={"thieving": 53},
        direct_skill_boostability={"thieving": "no"},
        prerequisite_quest_ids=("test_intermediate",),
        non_skill_conditions=(mask_condition(),),
    )

    return [ancestor, intermediate, destination]


def assess(profile, skills, verified=True):
    return assess_player_source_access(
        profile,
        skills,
        source_id="test_source",
        requirements_verified=verified,
    )


def complete_skills():
    return {
        "magic": 50,
        "crafting": 20,
        "thieving": 53,
    }


def test_resolver_preserves_direct_and_inherited_conditions():
    resolved = resolve_quest_skill_requirements(
        ["test_destination"],
        quest_chain(),
    )

    assert resolved.quest_ids == (
        "test_ancestor",
        "test_intermediate",
        "test_destination",
    )

    assert resolved.non_skill_conditions == (
        partial_condition(),
        mask_condition(),
    )

    assert resolved.effective_skill_requirements == {
        "magic": 50,
        "crafting": 20,
        "thieving": 53,
    }

    assert resolved.skill_boostability_thresholds == {
        "magic": {"no": 50},
        "crafting": {"yes": 20},
        "thieving": {"no": 53},
    }


def test_access_profile_preserves_full_condition_chain():
    profile = build_access_profile_from_quests(
        ["test_destination"],
        quest_chain(),
    )

    assert profile.non_skill_conditions == (
        partial_condition(),
        mask_condition(),
    )

    assert profile.effective_skill_requirements == {
        "magic": 50,
        "crafting": 20,
        "thieving": 53,
    }

    assert profile.skill_boostability_thresholds == {
        "magic": {"no": 50},
        "crafting": {"yes": 20},
        "thieving": {"no": 53},
    }


def test_shared_prerequisites_do_not_duplicate_conditions():
    resolved = resolve_quest_skill_requirements(
        ["test_intermediate", "test_destination"],
        quest_chain(),
    )

    assert resolved.non_skill_conditions == (
        partial_condition(),
        mask_condition(),
    )


def test_legacy_quests_keep_empty_condition_metadata():
    legacy = QuestRequirement(
        quest_id="test_legacy",
        display_name="Test Legacy",
        direct_skill_requirements={"magic": 50},
        direct_skill_boostability={"magic": "no"},
    )

    resolved = resolve_quest_skill_requirements(
        ["test_legacy"],
        [legacy],
    )

    profile = build_access_profile_from_quests(
        ["test_legacy"],
        [legacy],
    )

    assert legacy.non_skill_conditions == ()
    assert resolved.non_skill_conditions == ()
    assert profile.non_skill_conditions == ()

    assert assess(profile, {"magic": 50}) == "accessible"
    assert assess(profile, {"magic": 40}) == "inaccessible"


def test_partial_progression_alone_prevents_confirmed_access():
    quest = QuestRequirement(
        quest_id="test_ancestor",
        display_name="Test Ancestor",
        non_skill_conditions=(partial_condition(),),
    )

    profile = build_access_profile_from_quests(
        ["test_ancestor"],
        [quest],
    )

    assert assess(profile, {}) == "unknown"


def test_item_alternative_alone_does_not_prove_ownership():
    quest = QuestRequirement(
        quest_id="test_destination",
        display_name="Test Destination",
        non_skill_conditions=(mask_condition(),),
    )

    profile = build_access_profile_from_quests(
        ["test_destination"],
        [quest],
    )

    # No Slayer or gas-mask evidence is supplied.
    assert assess(profile, {}) == "unknown"


def test_satisfied_measurable_skills_do_not_verify_conditions():
    profile = build_access_profile_from_quests(
        ["test_destination"],
        quest_chain(),
    )

    assert assess(
        profile, complete_skills()
    ) == "unknown"


@pytest.mark.parametrize(
    ("skills", "expected"),
    (
        (
            {"magic": 40, "crafting": 20, "thieving": 53},
            "inaccessible",
        ),
        (
            {"magic": 50, "crafting": 20, "thieving": 40},
            "inaccessible",
        ),
        (
            {"magic": 50, "crafting": 19, "thieving": 53},
            "unknown",
        ),
        (
            {"magic": 50, "thieving": 53},
            "unknown",
        ),
        (
            {"magic": 50, "crafting": 20, "thieving": 53},
            "unknown",
        ),
    ),
)
def test_player_access_preserves_skill_evidence_rules(
    skills, expected,
):
    profile = build_access_profile_from_quests(
        ["test_destination"],
        quest_chain(),
    )

    assert assess(profile, skills) == expected


def test_unverified_requirement_source_stays_unknown():
    profile = build_access_profile_from_quests(
        ["test_destination"],
        quest_chain(),
    )

    assert assess(
        profile, complete_skills(), verified=False
    ) == "unknown"


def test_valid_quest_condition_list_is_normalised_to_tuple():
    conditions = [partial_condition()]

    quest = QuestRequirement(
        quest_id="test_ancestor",
        display_name="Test Ancestor",
        non_skill_conditions=conditions,
    )

    conditions.clear()

    assert quest.non_skill_conditions == (
        partial_condition(),
    )


def test_valid_access_profile_list_is_normalised_to_tuple():
    conditions = [partial_condition()]

    profile = AccessProfile(
        non_skill_conditions=conditions,
    )

    conditions.clear()

    assert profile.non_skill_conditions == (
        partial_condition(),
    )


@pytest.mark.parametrize(
    "conditions",
    (
        "invalid",
        {"condition_id": "invalid"},
        (object(),),
        (partial_condition(), partial_condition()),
        (partial_condition("wrong_quest"),),
    ),
)
def test_quest_rejects_invalid_or_mismatched_conditions(
    conditions,
):
    with pytest.raises(ValueError):
        QuestRequirement(
            quest_id="test_ancestor",
            display_name="Test Ancestor",
            non_skill_conditions=conditions,
        )


@pytest.mark.parametrize(
    "conditions",
    (
        "invalid",
        {"condition_id": "invalid"},
        (object(),),
        (partial_condition(), partial_condition()),
    ),
)
def test_access_profile_rejects_invalid_conditions(
    conditions,
):
    with pytest.raises(ValueError):
        AccessProfile(
            non_skill_conditions=conditions,
        )


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("quest_id", "not canonical"),
        ("condition_id", "not canonical"),
        ("detail", ""),
        ("source_wikitext_sha256", "invalid"),
        ("evidence_status", "VERIFIED"),
        ("planning_policy", "VERIFIED_PLAYER_ACCESS"),
        ("partial_quest_id", None),
        ("partial_quest_id", "test_ancestor"),
        (
            "alternative_skill_route",
            ("slayer", 10, "no"),
        ),
    ),
)
def test_partial_condition_rejects_invalid_metadata(
    field, invalid,
):
    kwargs = {
        "quest_id": "test_ancestor",
        "condition_id": "partial_the_restless_ghost",
        "condition_kind": "PARTIAL_QUEST_PROGRESSION",
        "detail": "Partial progress required",
        "source_wikitext_sha256": "a" * 64,
        "partial_quest_id": "the_restless_ghost",
    }

    kwargs[field] = invalid

    with pytest.raises(ValueError):
        QuestUnmeasuredCondition(**kwargs)


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("partial_quest_id", "the_restless_ghost"),
        ("alternative_skill_route", None),
        ("alternative_skill_route", ("slayer", 0, "no")),
        ("alternative_skill_route", ("slayer", True, "no")),
        ("alternative_skill_route", ("slayer", 10, "unknown")),
        ("condition_kind", "UNSUPPORTED"),
    ),
)
def test_alternative_condition_rejects_invalid_metadata(
    field, invalid,
):
    kwargs = {
        "quest_id": "test_destination",
        "condition_id": "gas_mask_from_plague_city",
        "condition_kind": "ALTERNATIVE_SKILL_OR_NON_SKILL",
        "detail": "Gas mask alternative",
        "source_wikitext_sha256": "b" * 64,
        "alternative_skill_route": ("slayer", 10, "no"),
    }

    kwargs[field] = invalid

    with pytest.raises(ValueError):
        QuestUnmeasuredCondition(**kwargs)


def test_same_condition_id_from_distinct_quests_is_preserved():
    first = partial_condition("test_ancestor")
    second = partial_condition("test_intermediate")

    profile = AccessProfile(
        non_skill_conditions=(first, second),
    )

    assert profile.non_skill_conditions == (
        first, second
    )


def test_source_fingerprints_remain_attached_to_conditions():
    profile = build_access_profile_from_quests(
        ["test_destination"],
        quest_chain(),
    )

    assert (
        profile.non_skill_conditions[0].source_wikitext_sha256
        == "a" * 64
    )

    assert (
        profile.non_skill_conditions[1].source_wikitext_sha256
        == "b" * 64
    )
