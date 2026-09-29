from utils.board_generation import AccessConfidence
from utils.osrs_quest_requirements import (
    QuestRequirement,
    build_access_profile_from_quests,
    resolve_quest_skill_requirements,
)


ZULRAH_REQUIRED_QUEST_IDS = (
    "regicide",
)

VORKATH_REQUIRED_QUEST_IDS = (
    "dragon_slayer_ii",
)

DARKMEYER_REQUIRED_QUEST_IDS = (
    "sins_of_the_father",
)


CURATED_QUEST_REQUIREMENTS = (
    # Regicide / Zulrah chain
    QuestRequirement(
        quest_id="plague_city",
        display_name="Plague City",
    ),
    QuestRequirement(
        quest_id="biohazard",
        display_name="Biohazard",
        prerequisite_quest_ids=(
            "plague_city",
        ),
    ),
    QuestRequirement(
        quest_id="underground_pass",
        display_name="Underground Pass",
        direct_skill_requirements={
            "Ranged": 25,
        },
        prerequisite_quest_ids=(
            "biohazard",
        ),
    ),
    QuestRequirement(
        quest_id="regicide",
        display_name="Regicide",
        direct_skill_requirements={
            "Crafting": 10,
            "Agility": 56,
        },
        prerequisite_quest_ids=(
            "underground_pass",
        ),
    ),

    # Dragon Slayer II / Vorkath chain
    QuestRequirement(
        quest_id="dragon_slayer_ii",
        display_name="Dragon Slayer II",
        direct_skill_requirements={
            "Magic": 75,
            "Smithing": 70,
            "Mining": 68,
            "Crafting": 62,
            "Agility": 60,
            "Thieving": 60,
            "Construction": 50,
            "Hitpoints": 50,
        },
        prerequisite_quest_ids=(
            "legends_quest",
            "dream_mentor",
            "a_tail_of_two_cats",
            "animal_magnetism",
            "ghosts_ahoy",
            "bone_voyage",
            "client_of_kourend",
        ),
    ),
    QuestRequirement(
        quest_id="legends_quest",
        display_name="Legends' Quest",
        direct_skill_requirements={
            "Agility": 50,
            "Crafting": 50,
            "Herblore": 45,
            "Magic": 56,
            "Mining": 52,
            "Prayer": 42,
            "Smithing": 50,
            "Strength": 50,
            "Thieving": 50,
            "Woodcutting": 50,
        },
        prerequisite_quest_ids=(
            "family_crest",
            "heroes_quest",
            "shilo_village",
            "underground_pass",
            "waterfall_quest",
        ),
    ),
    QuestRequirement(
        quest_id="family_crest",
        display_name="Family Crest",
        direct_skill_requirements={
            "Crafting": 40,
            "Mining": 40,
            "Smithing": 40,
            "Magic": 59,
        },
    ),
    QuestRequirement(
        quest_id="heroes_quest",
        display_name="Heroes' Quest",
        direct_skill_requirements={
            "Cooking": 53,
            "Fishing": 53,
            "Herblore": 25,
            "Mining": 50,
        },
        prerequisite_quest_ids=(
            "shield_of_arrav",
            "lost_city",
            "merlins_crystal",
            "dragon_slayer_i",
        ),
    ),
    QuestRequirement(
        quest_id="shield_of_arrav",
        display_name="Shield of Arrav",
    ),
    QuestRequirement(
        quest_id="lost_city",
        display_name="Lost City",
        direct_skill_requirements={
            "Crafting": 31,
            "Woodcutting": 36,
        },
    ),
    QuestRequirement(
        quest_id="merlins_crystal",
        display_name="Merlin's Crystal",
    ),
    QuestRequirement(
        quest_id="dragon_slayer_i",
        display_name="Dragon Slayer I",
    ),
    QuestRequirement(
        quest_id="shilo_village",
        display_name="Shilo Village",
        prerequisite_quest_ids=(
            "jungle_potion",
        ),
    ),
    QuestRequirement(
        quest_id="jungle_potion",
        display_name="Jungle Potion",
        prerequisite_quest_ids=(
            "druidic_ritual",
        ),
    ),
    QuestRequirement(
        quest_id="druidic_ritual",
        display_name="Druidic Ritual",
    ),
    QuestRequirement(
        quest_id="waterfall_quest",
        display_name="Waterfall Quest",
    ),
    QuestRequirement(
        quest_id="dream_mentor",
        display_name="Dream Mentor",
        prerequisite_quest_ids=(
            "lunar_diplomacy",
            "eadgars_ruse",
        ),
    ),
    QuestRequirement(
        quest_id="lunar_diplomacy",
        display_name="Lunar Diplomacy",
        direct_skill_requirements={
            "Defence": 40,
            "Firemaking": 49,
            "Magic": 65,
            "Mining": 60,
            "Woodcutting": 55,
            "Crafting": 61,
        },
        prerequisite_quest_ids=(
            "lost_city",
            "rune_mysteries",
            "shilo_village",
            "the_fremennik_trials",
        ),
    ),
    QuestRequirement(
        quest_id="rune_mysteries",
        display_name="Rune Mysteries",
    ),
    QuestRequirement(
        quest_id="the_fremennik_trials",
        display_name="The Fremennik Trials",
    ),
    QuestRequirement(
        quest_id="eadgars_ruse",
        display_name="Eadgar's Ruse",
        direct_skill_requirements={
            "Herblore": 31,
        },
        prerequisite_quest_ids=(
            "troll_stronghold",
            "druidic_ritual",
        ),
    ),
    QuestRequirement(
        quest_id="troll_stronghold",
        display_name="Troll Stronghold",
    ),
    QuestRequirement(
        quest_id="a_tail_of_two_cats",
        display_name="A Tail of Two Cats",
        prerequisite_quest_ids=(
            "gertrudes_cat",
            "icthlarins_little_helper",
        ),
    ),
    QuestRequirement(
        quest_id="gertrudes_cat",
        display_name="Gertrude's Cat",
    ),
    QuestRequirement(
        quest_id="icthlarins_little_helper",
        display_name="Icthlarin's Little Helper",
    ),
    QuestRequirement(
        quest_id="animal_magnetism",
        display_name="Animal Magnetism",
        direct_skill_requirements={
            "Crafting": 19,
            "Ranged": 30,
            "Slayer": 18,
            "Woodcutting": 35,
        },
        prerequisite_quest_ids=(
            "ernest_the_chicken",
            "priest_in_peril",
            "the_restless_ghost",
        ),
    ),
    QuestRequirement(
        quest_id="ernest_the_chicken",
        display_name="Ernest the Chicken",
    ),
    QuestRequirement(
        quest_id="ghosts_ahoy",
        display_name="Ghosts Ahoy",
        direct_skill_requirements={
            "Agility": 25,
            "Cooking": 20,
        },
        prerequisite_quest_ids=(
            "priest_in_peril",
            "the_restless_ghost",
        ),
    ),
    QuestRequirement(
        quest_id="bone_voyage",
        display_name="Bone Voyage",
        prerequisite_quest_ids=(
            "the_dig_site",
        ),
    ),
    QuestRequirement(
        quest_id="the_dig_site",
        display_name="The Dig Site",
        direct_skill_requirements={
            "Agility": 10,
            "Herblore": 10,
            "Thieving": 25,
        },
    ),
    QuestRequirement(
        quest_id="client_of_kourend",
        display_name="Client of Kourend",
    ),

    # Sins of the Father / Darkmeyer chain
    QuestRequirement(
        quest_id="sins_of_the_father",
        display_name="Sins of the Father",
        direct_skill_requirements={
            "Woodcutting": 62,
            "Fletching": 60,
            "Crafting": 56,
            "Agility": 52,
            "Attack": 50,
            "Slayer": 50,
            "Magic": 49,
        },
        prerequisite_quest_ids=(
            "vampyre_slayer",
            "a_taste_of_hope",
        ),
    ),
    QuestRequirement(
        quest_id="vampyre_slayer",
        display_name="Vampyre Slayer",
    ),
    QuestRequirement(
        quest_id="a_taste_of_hope",
        display_name="A Taste of Hope",
        direct_skill_requirements={
            "Crafting": 48,
            "Agility": 45,
            "Attack": 40,
            "Herblore": 40,
            "Slayer": 38,
        },
        prerequisite_quest_ids=(
            "darkness_of_hallowvale",
        ),
    ),
    QuestRequirement(
        quest_id="darkness_of_hallowvale",
        display_name="Darkness of Hallowvale",
        direct_skill_requirements={
            "Construction": 5,
            "Mining": 20,
            "Thieving": 22,
            "Agility": 26,
            "Crafting": 32,
            "Magic": 33,
            "Strength": 40,
        },
        prerequisite_quest_ids=(
            "in_aid_of_the_myreque",
        ),
    ),
    QuestRequirement(
        quest_id="in_aid_of_the_myreque",
        display_name="In Aid of the Myreque",
        direct_skill_requirements={
            "Agility": 25,
            "Crafting": 25,
            "Mining": 15,
            "Magic": 7,
        },
        prerequisite_quest_ids=(
            "in_search_of_the_myreque",
        ),
    ),
    QuestRequirement(
        quest_id="in_search_of_the_myreque",
        display_name="In Search of the Myreque",
        prerequisite_quest_ids=(
            "nature_spirit",
        ),
    ),
    QuestRequirement(
        quest_id="nature_spirit",
        display_name="Nature Spirit",
        prerequisite_quest_ids=(
            "priest_in_peril",
            "the_restless_ghost",
        ),
    ),
    QuestRequirement(
        quest_id="priest_in_peril",
        display_name="Priest in Peril",
    ),
    QuestRequirement(
        quest_id="the_restless_ghost",
        display_name="The Restless Ghost",
    ),
)


def get_curated_quest_requirements():
    return CURATED_QUEST_REQUIREMENTS


def resolve_curated_quest_skill_requirements(required_quest_ids):
    return resolve_quest_skill_requirements(
        required_quest_ids=required_quest_ids,
        quest_requirements=CURATED_QUEST_REQUIREMENTS,
    )


def build_curated_access_profile_from_quests(
    required_quest_ids,
    recommended_skill_requirements=None,
    additional_access_flags=None,
    access_confidence=AccessConfidence.MEDIUM,
):
    return build_access_profile_from_quests(
        required_quest_ids=required_quest_ids,
        quest_requirements=CURATED_QUEST_REQUIREMENTS,
        recommended_skill_requirements=recommended_skill_requirements,
        additional_access_flags=additional_access_flags,
        access_confidence=access_confidence,
    )
