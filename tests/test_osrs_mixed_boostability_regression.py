"""Protect access assessment against mixed boostability regressions."""

from dataclasses import replace

import pytest

from utils.board_generation import AccessProfile
from utils.osrs_content_access import (
    build_access_profile_for_content,
)
from utils.osrs_player_access import (
    assess_player_source_access,
)
from utils.osrs_quest_data import (
    get_curated_quest_requirements,
)
from utils.osrs_quest_requirements import (
    resolve_quest_skill_requirements,
)


def assess_magic(level, required, thresholds):
    profile = AccessProfile(
        effective_skill_requirements={
            "magic": required,
        },
        skill_boostability_thresholds={
            "magic": thresholds,
        },
    )

    return assess_player_source_access(
        profile,
        {"magic": level},
        source_id="synthetic_verified_source",
        requirements_verified=True,
    )


@pytest.mark.parametrize(
    "level,required,thresholds,expected",
    [
        (1, 75, {"yes": 59, "unknown": 75}, "inaccessible"),
        (50, 75, {"yes": 59, "unknown": 75}, "inaccessible"),
        (58, 75, {"yes": 59, "unknown": 75}, "inaccessible"),
        (59, 75, {"yes": 59, "unknown": 75}, "inaccessible"),
        (74, 75, {"yes": 59, "unknown": 75}, "inaccessible"),
        (75, 75, {"yes": 59, "unknown": 75}, "accessible"),
        (1, 53, {"yes": 53}, "unknown"),
        (53, 53, {"yes": 53}, "accessible"),
        (1, 53, {"unknown": 20, "yes": 53}, "inaccessible"),
        (20, 53, {"unknown": 20, "yes": 53}, "unknown"),
        (53, 53, {"unknown": 20, "yes": 53}, "accessible"),
        (1, 40, {"no": 40}, "inaccessible"),
        (40, 40, {"no": 40}, "accessible"),
    ],
)
def test_mixed_boostability_thresholds(
    level,
    required,
    thresholds,
    expected,
):
    assert assess_magic(
        level,
        required,
        thresholds,
    ) == expected


def test_vorkath_family_crest_mixed_thresholds():
    """The test must work before and after Family Crest activation."""

    curated = list(get_curated_quest_requirements())

    family = next(
        quest
        for quest in curated
        if quest.quest_id == "family_crest"
    )

    assert family.direct_skill_requirements == {
        "crafting": 40,
        "mining": 40,
        "smithing": 40,
        "magic": 59,
    }

    approved_boostability = {
        "crafting": "yes",
        "mining": "yes",
        "smithing": "yes",
        "magic": "yes",
    }

    # Build both historical and approved states in memory.
    # This remains valid after the actual activation.
    historical_catalogue = [
        replace(
            quest,
            direct_skill_boostability={},
        )
        if quest.quest_id == "family_crest"
        else quest
        for quest in curated
    ]

    approved_catalogue = [
        replace(
            quest,
            direct_skill_boostability=approved_boostability,
        )
        if quest.quest_id == "family_crest"
        else quest
        for quest in curated
    ]

    historical = resolve_quest_skill_requirements(
        ["dragon_slayer_ii"],
        historical_catalogue,
    )

    approved = resolve_quest_skill_requirements(
        ["dragon_slayer_ii"],
        approved_catalogue,
    )

    assert "family_crest" in historical.quest_ids
    assert historical.quest_ids == approved.quest_ids

    assert (
        historical.effective_skill_requirements
        == approved.effective_skill_requirements
    )

    assert historical.effective_skill_requirements[
        "magic"
    ] == 75

    assert historical.skill_boostability_thresholds[
        "magic"
    ] == {"yes": 56, "unknown": 75}

    assert approved.skill_boostability_thresholds[
        "magic"
    ] == {
        "yes": 59,
        "unknown": 75,
    }

    current_profile = build_access_profile_for_content(
        "vorkath"
    )

    assert (
        current_profile.effective_skill_requirements
        == historical.effective_skill_requirements
    )

    historical_profile = replace(
        current_profile,
        skill_boostability_thresholds=(
            historical.skill_boostability_thresholds
        ),
    )

    approved_profile = replace(
        current_profile,
        skill_boostability_thresholds=(
            approved.skill_boostability_thresholds
        ),
    )

    # Low Magic levels block Vorkath in both states.
    for magic_level in (1, 50, 59, 74):
        levels = {
            "magic": magic_level,
            "slayer": 70,
        }

        for profile in (
            historical_profile,
            approved_profile,
        ):
            assert assess_player_source_access(
                profile,
                levels,
                source_id="vorkath",
                requirements_verified=True,
            ) == "inaccessible"

    # Higher Magic alone cannot establish access
    # when the remaining WOM skill evidence is missing.
    for profile in (
        historical_profile,
        approved_profile,
    ):
        assert assess_player_source_access(
            profile,
            {"magic": 75, "slayer": 70},
            source_id="vorkath",
            requirements_verified=True,
        ) == "unknown"
