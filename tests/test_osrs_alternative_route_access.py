"""Alternative skill-route eligibility regression tests.

An original numerical route can satisfy a verified OR
requirement without verifying the alternative item or
travel route.

Unmeasured conditions never prove player inventory,
partial quest progress or travel access.
"""

import pytest

from utils.board_generation import AccessProfile
from utils.osrs_player_access import assess_player_source_access
from utils.osrs_quest_data import get_curated_quest_requirements
from utils.osrs_quest_requirements import (
    QuestRequirement,
    QuestUnmeasuredCondition,
    build_access_profile_from_quests,
)


def mask():
    return QuestUnmeasuredCondition(
        quest_id="desert_treasure_i",
        condition_id="gas_mask_from_plague_city",
        condition_kind="ALTERNATIVE_SKILL_OR_NON_SKILL",
        detail="10 Slayer or a gas mask",
        source_wikitext_sha256="a" * 64,
        alternative_skill_route=("slayer", 10, "no"),
    )


def charter():
    return QuestUnmeasuredCondition(
        quest_id="roving_elves",
        condition_id="charter_ship_to_elven_woods",
        condition_kind="ALTERNATIVE_SKILL_OR_NON_SKILL",
        detail="56 Agility or charter-ship access",
        source_wikitext_sha256="b" * 64,
        alternative_skill_route=("agility", 56, "yes"),
    )


def partial():
    return QuestUnmeasuredCondition(
        quest_id="creature_of_fenkenstrain",
        condition_id="partial_the_restless_ghost",
        condition_kind="PARTIAL_QUEST_PROGRESSION",
        detail="Partial Restless Ghost progression",
        source_wikitext_sha256="c" * 64,
        partial_quest_id="the_restless_ghost",
    )


def profile(*conditions):
    return AccessProfile(
        effective_skill_requirements={"magic": 50},
        skill_boostability_thresholds={
            "magic": {"no": 50},
        },
        non_skill_conditions=conditions,
    )


def assess(access_profile, skills, verified=True):
    return assess_player_source_access(
        access_profile,
        skills,
        source_id="test_source",
        requirements_verified=verified,
    )


@pytest.mark.parametrize(
    ("slayer", "expected"),
    (
        (10, "accessible"),
        (11, "accessible"),
        (99, "accessible"),
        (9, "unknown"),
        (1, "unknown"),
        (0, "unknown"),
        (None, "unknown"),
        (True, "unknown"),
        (10.0, "unknown"),
        ("10", "unknown"),
    ),
)
def test_original_slayer_route_or_unknown_gas_mask(
    slayer, expected,
):
    levels = {"magic": 50, "slayer": slayer}

    assert assess(profile(mask()), levels) == expected


def test_missing_slayer_evidence_keeps_gas_mask_unknown():
    assert assess(
        profile(mask()),
        {"magic": 50},
    ) == "unknown"


@pytest.mark.parametrize(
    ("agility", "expected"),
    (
        (56, "accessible"),
        (57, "accessible"),
        (99, "accessible"),
        (55, "unknown"),
        (1, "unknown"),
        (None, "unknown"),
        (True, "unknown"),
        ("56", "unknown"),
    ),
)
def test_original_agility_route_or_unknown_charter(
    agility, expected,
):
    levels = {"magic": 50, "agility": agility}

    assert assess(profile(charter()), levels) == expected


@pytest.mark.parametrize(
    ("magic", "expected"),
    (
        (50, "accessible"),
        (49, "inaccessible"),
        (1, "inaccessible"),
        (None, "unknown"),
        (True, "unknown"),
        ("50", "unknown"),
    ),
)
def test_other_mandatory_skill_is_never_waived(
    magic, expected,
):
    levels = {"magic": magic, "slayer": 10}

    assert assess(profile(mask()), levels) == expected


@pytest.mark.parametrize(
    "condition",
    (
        mask(),
        charter(),
        partial(),
    ),
)
def test_unverified_source_never_establishes_access(
    condition,
):
    assert assess(
        profile(condition),
        {
            "magic": 50,
            "slayer": 10,
            "agility": 56,
        },
        verified=False,
    ) == "unknown"


def test_unmeasured_partial_progression_always_remains_unknown():
    assert assess(
        profile(partial()),
        {"magic": 50},
    ) == "unknown"


def test_satisfied_slayer_route_does_not_waive_partial_progress():
    assert assess(
        profile(mask(), partial()),
        {"magic": 50, "slayer": 10},
    ) == "unknown"


@pytest.mark.parametrize(
    ("slayer", "agility", "expected"),
    (
        (10, 56, "accessible"),
        (9, 56, "unknown"),
        (10, 55, "unknown"),
        (9, 55, "unknown"),
    ),
)
def test_multiple_or_conditions_must_each_be_satisfied(
    slayer, agility, expected,
):
    assert assess(
        profile(mask(), charter()),
        {
            "magic": 50,
            "slayer": slayer,
            "agility": agility,
        },
    ) == expected


def test_unboostable_inherited_threshold_cannot_be_bypassed():
    access_profile = AccessProfile(
        effective_skill_requirements={"agility": 56},
        skill_boostability_thresholds={
            "agility": {"no": 56},
        },
        non_skill_conditions=(charter(),),
    )

    assert assess(
        access_profile,
        {"agility": 55},
    ) == "inaccessible"

    assert assess(
        access_profile,
        {"agility": 56},
    ) == "accessible"


def test_boostable_inherited_threshold_remains_uncertain():
    access_profile = AccessProfile(
        effective_skill_requirements={"agility": 56},
        skill_boostability_thresholds={
            "agility": {"yes": 56},
        },
        non_skill_conditions=(charter(),),
    )

    assert assess(
        access_profile,
        {"agility": 55},
    ) == "unknown"

    assert assess(
        access_profile,
        {"agility": 56},
    ) == "accessible"


def test_actual_regicide_chain_preserves_inherited_agility():
    roving_elves = QuestRequirement(
        quest_id="roving_elves",
        display_name="Roving Elves",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(
            "regicide",
            "waterfall_quest",
        ),
        non_skill_conditions=(charter(),),
    )

    catalogue = [
        quest
        for quest in get_curated_quest_requirements()
        if quest.quest_id != "roving_elves"
    ] + [roving_elves]

    access_profile = build_access_profile_from_quests(
        ["roving_elves"],
        catalogue,
    )

    assert access_profile.effective_skill_requirements[
        "agility"
    ] == 56

    assert access_profile.skill_boostability_thresholds[
        "agility"
    ]["yes"] == 56

    assert access_profile.non_skill_conditions == (
        charter(),
    )

    satisfied = dict(
        access_profile.effective_skill_requirements
    )

    assert assess(
        access_profile,
        satisfied,
    ) == "accessible"

    insufficient = dict(satisfied)
    insufficient["agility"] = 55

    assert assess(
        access_profile,
        insufficient,
    ) == "unknown"


def test_verified_skill_route_does_not_claim_item_ownership():
    condition = mask()

    assert condition.evidence_status == (
        "NOT_INDEPENDENTLY_MEASURED"
    )

    assert condition.planning_policy == (
        "ASSUMED_FOR_PLANNING_ONLY"
    )

    assert assess(
        profile(condition),
        {"magic": 50, "slayer": 10},
    ) == "accessible"

    assert condition.evidence_status == (
        "NOT_INDEPENDENTLY_MEASURED"
    )

    assert condition.condition_id == (
        "gas_mask_from_plague_city"
    )


def test_legacy_profile_remains_accessible():
    assert assess(
        profile(),
        {"magic": 50},
    ) == "accessible"


def test_legacy_profile_unmet_skill_remains_inaccessible():
    assert assess(
        profile(),
        {"magic": 49},
    ) == "inaccessible"
