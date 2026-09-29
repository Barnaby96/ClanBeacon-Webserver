from utils.board_generation import AccessConfidence, AccessFlag
from utils.osrs_quest_data import (
    DARKMEYER_REQUIRED_QUEST_IDS,
    VORKATH_REQUIRED_QUEST_IDS,
    ZULRAH_REQUIRED_QUEST_IDS,
    build_curated_access_profile_from_quests,
    get_curated_quest_requirements,
    resolve_curated_quest_skill_requirements,
)


def test_curated_quest_requirement_ids_are_unique():
    quest_ids = [
        quest.quest_id
        for quest in get_curated_quest_requirements()
    ]

    assert len(quest_ids) == len(set(quest_ids))


def test_zulrah_regicide_chain_resolves_expected_skill_requirements():
    resolved = resolve_curated_quest_skill_requirements(
        ZULRAH_REQUIRED_QUEST_IDS
    )

    assert resolved.effective_skill_requirements == {
        "agility": 56,
        "ranged": 25,
        "crafting": 10,
    }
    assert resolved.quest_ids == (
        "plague_city",
        "biohazard",
        "underground_pass",
        "regicide",
    )
    assert AccessFlag.QUEST_LOCKED in resolved.access_flags


def test_vorkath_dragon_slayer_ii_chain_resolves_expected_skill_requirements():
    resolved = resolve_curated_quest_skill_requirements(
        VORKATH_REQUIRED_QUEST_IDS
    )

    assert resolved.effective_skill_requirements == {
        "magic": 75,
        "smithing": 70,
        "mining": 68,
        "crafting": 62,
        "agility": 60,
        "thieving": 60,
        "woodcutting": 55,
        "cooking": 53,
        "fishing": 53,
        "construction": 50,
        "hitpoints": 50,
        "strength": 50,
        "firemaking": 49,
        "herblore": 45,
        "prayer": 42,
        "defence": 40,
        "ranged": 30,
        "slayer": 18,
    }

    assert "dragon_slayer_ii" in resolved.quest_ids
    assert "legends_quest" in resolved.quest_ids
    assert "dream_mentor" in resolved.quest_ids
    assert "animal_magnetism" in resolved.quest_ids
    assert AccessFlag.QUEST_LOCKED in resolved.access_flags


def test_darkmeyer_sins_of_the_father_chain_resolves_expected_skill_requirements():
    resolved = resolve_curated_quest_skill_requirements(
        DARKMEYER_REQUIRED_QUEST_IDS
    )

    assert resolved.effective_skill_requirements == {
        "woodcutting": 62,
        "fletching": 60,
        "crafting": 56,
        "agility": 52,
        "attack": 50,
        "slayer": 50,
        "magic": 49,
        "herblore": 40,
        "strength": 40,
        "thieving": 22,
        "mining": 20,
        "construction": 5,
    }

    assert resolved.quest_ids == (
        "vampyre_slayer",
        "priest_in_peril",
        "the_restless_ghost",
        "nature_spirit",
        "in_search_of_the_myreque",
        "in_aid_of_the_myreque",
        "darkness_of_hallowvale",
        "a_taste_of_hope",
        "sins_of_the_father",
    )
    assert AccessFlag.QUEST_LOCKED in resolved.access_flags


def test_curated_access_profile_from_quests_can_add_recommended_skills():
    profile = build_curated_access_profile_from_quests(
        required_quest_ids=ZULRAH_REQUIRED_QUEST_IDS,
        recommended_skill_requirements={
            "Ranged": 75,
            "Magic": 75,
        },
        access_confidence=AccessConfidence.MEDIUM,
    )

    assert profile.effective_skill_requirements == {
        "agility": 56,
        "ranged": 25,
        "crafting": 10,
    }
    assert profile.recommended_skill_requirements == {
        "ranged": 75,
        "magic": 75,
    }
    assert profile.access_flags == frozenset(
        {
            AccessFlag.QUEST_LOCKED,
        }
    )
    assert profile.access_confidence == AccessConfidence.MEDIUM
