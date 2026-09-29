import pytest

from utils.board_generation import AccessConfidence, AccessFlag
from utils.osrs_quest_requirements import (
    QuestRequirement,
    QuestRequirementError,
    build_access_profile_from_quests,
    resolve_quest_skill_requirements,
)


def test_resolve_quest_skill_requirements_flattens_prerequisite_chain():
    quests = [
        QuestRequirement(
            quest_id="starter_quest",
            display_name="Starter Quest",
            direct_skill_requirements={
                "Thieving": 25,
                "Agility": 20,
            },
        ),
        QuestRequirement(
            quest_id="middle_quest",
            display_name="Middle Quest",
            direct_skill_requirements={
                "Agility": 40,
            },
            prerequisite_quest_ids=(
                "starter_quest",
            ),
        ),
        QuestRequirement(
            quest_id="final_quest",
            display_name="Final Quest",
            direct_skill_requirements={
                "Magic": 50,
            },
            prerequisite_quest_ids=(
                "middle_quest",
            ),
        ),
    ]

    resolved = resolve_quest_skill_requirements(
        [
            "final_quest"
        ],
        quests
    )

    assert resolved.quest_ids == (
        "starter_quest",
        "middle_quest",
        "final_quest",
    )
    assert resolved.effective_skill_requirements == {
        "thieving": 25,
        "agility": 40,
        "magic": 50,
    }
    assert AccessFlag.QUEST_LOCKED in resolved.access_flags


def test_resolve_quest_skill_requirements_keeps_highest_required_level():
    quests = [
        QuestRequirement(
            quest_id="first_quest",
            display_name="First Quest",
            direct_skill_requirements={
                "Agility": 30,
            },
        ),
        QuestRequirement(
            quest_id="second_quest",
            display_name="Second Quest",
            direct_skill_requirements={
                "Agility": 60,
            },
            prerequisite_quest_ids=(
                "first_quest",
            ),
        ),
    ]

    resolved = resolve_quest_skill_requirements(
        [
            "second_quest"
        ],
        quests
    )

    assert resolved.effective_skill_requirements == {
        "agility": 60,
    }


def test_resolve_quest_skill_requirements_rejects_unknown_quest():
    with pytest.raises(
        QuestRequirementError,
        match="Unknown quest requirement id"
    ):
        resolve_quest_skill_requirements(
            [
                "missing_quest"
            ],
            []
        )


def test_resolve_quest_skill_requirements_rejects_circular_chain():
    quests = [
        QuestRequirement(
            quest_id="quest_a",
            display_name="Quest A",
            prerequisite_quest_ids=(
                "quest_b",
            ),
        ),
        QuestRequirement(
            quest_id="quest_b",
            display_name="Quest B",
            prerequisite_quest_ids=(
                "quest_a",
            ),
        ),
    ]

    with pytest.raises(
        QuestRequirementError,
        match="Circular quest requirement chain"
    ):
        resolve_quest_skill_requirements(
            [
                "quest_a"
            ],
            quests
        )


def test_build_access_profile_from_quests_combines_effective_and_recommended_skills():
    quests = [
        QuestRequirement(
            quest_id="boss_unlock",
            display_name="Boss Unlock",
            direct_skill_requirements={
                "Agility": 56,
                "Crafting": 10,
            },
        )
    ]

    profile = build_access_profile_from_quests(
        required_quest_ids=[
            "boss_unlock"
        ],
        quest_requirements=quests,
        recommended_skill_requirements={
            "Ranged": 75,
            "Magic": 75,
        },
        additional_access_flags={
            AccessFlag.DANGEROUS_DEATH
        },
        access_confidence=AccessConfidence.MEDIUM,
    )

    assert profile.effective_skill_requirements == {
        "agility": 56,
        "crafting": 10,
    }
    assert profile.recommended_skill_requirements == {
        "ranged": 75,
        "magic": 75,
    }
    assert profile.access_flags == frozenset(
        {
            AccessFlag.QUEST_LOCKED,
            AccessFlag.DANGEROUS_DEATH,
        }
    )
    assert profile.access_confidence == AccessConfidence.MEDIUM
