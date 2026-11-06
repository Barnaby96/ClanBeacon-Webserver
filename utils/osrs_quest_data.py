from utils.board_generation import AccessConfidence
from utils.osrs_quest_requirements import (
    QuestRequirement,
    QuestUnmeasuredCondition,
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
    QuestRequirement(
        quest_id='a_night_at_the_theatre',
        display_name='A Night at the Theatre',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('a_taste_of_hope',),
    ),
    QuestRequirement(
        quest_id='cold_war',
        display_name='Cold War',
        direct_skill_requirements={'hunter': 10, 'agility': 30, 'crafting': 30, 'construction': 34, 'thieving': 15},
        direct_skill_boostability={'hunter': 'no', 'agility': 'no', 'crafting': 'no', 'construction': 'no', 'thieving': 'no'},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='perilous_moons',
        display_name='Perilous Moons',
        direct_skill_requirements={'slayer': 48, 'hunter': 20, 'fishing': 20, 'runecraft': 20, 'construction': 10},
        direct_skill_boostability={'slayer': 'no', 'hunter': 'no', 'fishing': 'no', 'runecraft': 'no', 'construction': 'no'},
        prerequisite_quest_ids=('twilights_promise',),
    ),
    QuestRequirement(
        quest_id='the_forsaken_tower',
        display_name='The Forsaken Tower',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('client_of_kourend',),
    ),
    QuestRequirement(
        quest_id='the_heart_of_darkness',
        display_name='The Heart of Darkness',
        direct_skill_requirements={'mining': 55, 'thieving': 48, 'slayer': 48, 'agility': 46},
        direct_skill_boostability={'mining': 'no', 'thieving': 'no', 'slayer': 'no', 'agility': 'no'},
        prerequisite_quest_ids=('twilights_promise',),
    ),
    QuestRequirement(
        quest_id='the_path_of_glouphrie',
        display_name='The Path of Glouphrie',
        direct_skill_requirements={'strength': 60, 'slayer': 56, 'thieving': 56, 'ranged': 47, 'agility': 45},
        direct_skill_boostability={'strength': 'no', 'slayer': 'no', 'thieving': 'no', 'ranged': 'no', 'agility': 'no'},
        prerequisite_quest_ids=('the_eyes_of_glouphrie', 'waterfall_quest', 'tree_gnome_village'),
    ),
    QuestRequirement(
        quest_id='troll_romance',
        display_name='Troll Romance',
        direct_skill_requirements={'agility': 28},
        direct_skill_boostability={'agility': 'yes'},
        prerequisite_quest_ids=('troll_stronghold',),
    ),
    QuestRequirement(
        quest_id='watchtower',
        display_name='Watchtower',
        direct_skill_requirements={'magic': 14, 'thieving': 15, 'agility': 25, 'herblore': 14, 'mining': 40},
        direct_skill_boostability={'magic': 'yes', 'thieving': 'yes', 'agility': 'yes', 'herblore': 'yes', 'mining': 'yes'},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='beneath_cursed_sands',
        display_name='Beneath Cursed Sands',
        direct_skill_requirements={'agility': 62, 'crafting': 55, 'firemaking': 55},
        direct_skill_boostability={'agility': 'no', 'crafting': 'no', 'firemaking': 'no'},
        prerequisite_quest_ids=('contact',),
    ),
    QuestRequirement(
        quest_id='death_on_the_isle',
        display_name='Death on the Isle',
        direct_skill_requirements={'thieving': 34, 'agility': 32},
        direct_skill_boostability={'thieving': 'no', 'agility': 'no'},
        prerequisite_quest_ids=('children_of_the_sun',),
    ),
    QuestRequirement(
        quest_id='fairytale_ii_cure_a_queen',
        display_name='Fairytale II - Cure a Queen',
        direct_skill_requirements={'thieving': 40, 'farming': 49, 'herblore': 57},
        direct_skill_boostability={'thieving': 'no', 'farming': 'yes', 'herblore': 'yes'},
        prerequisite_quest_ids=('fairytale_i_growing_pains',),
    ),
    QuestRequirement(
        quest_id='fallen_from_grace',
        display_name='Fallen From Grace',
        direct_skill_requirements={'sailing': 62, 'crafting': 60, 'runecraft': 47, 'mining': 53},
        direct_skill_boostability={'sailing': 'no', 'crafting': 'no', 'runecraft': 'no', 'mining': 'no'},
        prerequisite_quest_ids=('pandemonium',),
    ),
    QuestRequirement(
        quest_id='one_small_favour',
        display_name='One Small Favour',
        direct_skill_requirements={'agility': 36, 'crafting': 25, 'herblore': 18, 'smithing': 30},
        direct_skill_boostability={'agility': 'yes', 'crafting': 'yes', 'herblore': 'yes', 'smithing': 'yes'},
        prerequisite_quest_ids=('rune_mysteries', 'shilo_village'),
    ),
    QuestRequirement(
        quest_id='the_eyes_of_glouphrie',
        display_name='The Eyes of Glouphrie',
        direct_skill_requirements={'construction': 5, 'magic': 46},
        direct_skill_boostability={'construction': 'no', 'magic': 'no'},
        prerequisite_quest_ids=('the_grand_tree',),
    ),
    QuestRequirement(
        quest_id='twilights_promise',
        display_name="Twilight's Promise",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('children_of_the_sun',),
    ),
    QuestRequirement(
        quest_id='contact',
        display_name='Contact!',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('prince_ali_rescue', 'icthlarins_little_helper'),
    ),
    QuestRequirement(
        quest_id='fairytale_i_growing_pains',
        display_name='Fairytale I - Growing Pains',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('lost_city', 'nature_spirit'),
    ),
    QuestRequirement(
        quest_id='making_history',
        display_name='Making History',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('priest_in_peril', 'the_restless_ghost'),
    ),
    QuestRequirement(
        quest_id='throne_of_miscellania',
        display_name='Throne of Miscellania',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('heroes_quest', 'the_fremennik_trials'),
    ),
    QuestRequirement(
        quest_id='zogre_flesh_eaters',
        display_name='Zogre Flesh Eaters',
        direct_skill_requirements={'smithing': 4, 'herblore': 8, 'ranged': 30},
        direct_skill_boostability={'smithing': 'yes', 'herblore': 'yes', 'ranged': 'no'},
        prerequisite_quest_ids=('big_chompy_bird_hunting', 'jungle_potion'),
    ),
    QuestRequirement(
        quest_id='troubled_tortugans',
        display_name='Troubled Tortugans',
        direct_skill_requirements={'slayer': 51, 'construction': 48, 'sailing': 45, 'hunter': 45, 'woodcutting': 40, 'crafting': 34},
        direct_skill_boostability={'slayer': 'no', 'construction': 'no', 'sailing': 'no', 'hunter': 'no', 'woodcutting': 'no', 'crafting': 'no'},
        prerequisite_quest_ids=('pandemonium',),
    ),
    QuestRequirement(
        quest_id='at_first_light',
        display_name='At First Light',
        direct_skill_requirements={'hunter': 46, 'herblore': 30, 'construction': 27},
        direct_skill_boostability={'hunter': 'no', 'herblore': 'no', 'construction': 'no'},
        prerequisite_quest_ids=('children_of_the_sun', 'eagles_peak'),
    ),
    QuestRequirement(
        quest_id='ethically_acquired_antiquities',
        display_name='Ethically Acquired Antiquities',
        direct_skill_requirements={'thieving': 25},
        direct_skill_boostability={'thieving': 'no'},
        prerequisite_quest_ids=('children_of_the_sun', 'shield_of_arrav'),
    ),
    QuestRequirement(
        quest_id='prying_times',
        display_name='Prying Times',
        direct_skill_requirements={'smithing': 30, 'sailing': 12},
        direct_skill_boostability={'smithing': 'no', 'sailing': 'no'},
        prerequisite_quest_ids=('pandemonium', 'the_knights_sword'),
    ),
    QuestRequirement(
        quest_id='children_of_the_sun',
        display_name='Children of the Sun',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='pandemonium',
        display_name='Pandemonium',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='romeo_and_juliet',
        display_name='Romeo & Juliet',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='a_souls_bane',
        display_name="A Soul's Bane",
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='clock_tower',
        display_name='Clock Tower',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='demon_slayer',
        display_name='Demon Slayer',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='dorics_quest',
        display_name="Doric's Quest",
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='fight_arena',
        display_name='Fight Arena',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='hazeel_cult',
        display_name='Hazeel Cult',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='monks_friend',
        display_name="Monk's Friend",
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='observatory_quest',
        display_name='Observatory Quest',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='pirates_treasure',
        display_name="Pirate's Treasure",
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='prince_ali_rescue',
        display_name='Prince Ali Rescue',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='rag_and_bone_man_i',
        display_name='Rag and Bone Man I',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='the_ides_of_milk',
        display_name='The Ides of Milk',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='tree_gnome_village',
        display_name='Tree Gnome Village',
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='witchs_house',
        display_name="Witch's House",
        direct_skill_requirements={
        },
        direct_skill_boostability={
        },
    ),
    QuestRequirement(
        quest_id='forgettable_tale',
        display_name='Forgettable Tale...',
        direct_skill_requirements={
            'cooking': 22,
            'farming': 17,
        },
        direct_skill_boostability={
            'cooking': 'yes',
            'farming': 'yes',
        },
        prerequisite_quest_ids=('the_giant_dwarf', 'fishing_contest'),
    ),
    QuestRequirement(
        quest_id='the_grand_tree',
        display_name='The Grand Tree',
        direct_skill_requirements={
            'agility': 25,
        },
        direct_skill_boostability={
            'agility': 'yes',
        },
    ),
    QuestRequirement(
        quest_id='big_chompy_bird_hunting',
        display_name='Big Chompy Bird Hunting',
        direct_skill_requirements={
            'fletching': 5,
            'cooking': 30,
            'ranged': 30,
        },
        direct_skill_boostability={
            'fletching': 'yes',
            'cooking': 'yes',
            'ranged': 'no',
        },
    ),
    QuestRequirement(
        quest_id='the_giant_dwarf',
        display_name='The Giant Dwarf',
        direct_skill_requirements={
            'crafting': 12,
            'firemaking': 16,
            'magic': 33,
            'thieving': 14,
        },
        direct_skill_boostability={
            'crafting': 'yes',
            'firemaking': 'yes',
            'magic': 'yes',
            'thieving': 'yes',
        },
    ),
    QuestRequirement(
        quest_id='spirits_of_the_elid',
        display_name='Spirits of the Elid',
        direct_skill_requirements={
            'magic': 33,
            'ranged': 37,
            'mining': 37,
            'thieving': 37,
        },
        direct_skill_boostability={
            'magic': 'yes',
            'ranged': 'yes',
            'mining': 'yes',
            'thieving': 'yes',
        },
    ),
    QuestRequirement(
        quest_id='the_ascent_of_arceuus',
        display_name='The Ascent of Arceuus',
        direct_skill_requirements={
            'hunter': 12,
        },
        direct_skill_boostability={
            'hunter': 'no',
        },
        prerequisite_quest_ids=('client_of_kourend',),
    ),
    QuestRequirement(
        quest_id='the_depths_of_despair',
        display_name='The Depths of Despair',
        direct_skill_requirements={
            'agility': 18,
        },
        direct_skill_boostability={
            'agility': 'no',
        },
        prerequisite_quest_ids=('client_of_kourend',),
    ),
    QuestRequirement(
        quest_id='holy_grail',
        display_name='Holy Grail',
        direct_skill_requirements={
            'attack': 20,
        },
        direct_skill_boostability={
            'attack': 'no',
        },
        prerequisite_quest_ids=('merlins_crystal',),
    ),
    QuestRequirement(
        quest_id='the_queen_of_thieves',
        display_name='The Queen of Thieves',
        direct_skill_requirements={
            'thieving': 20,
        },
        direct_skill_boostability={
            'thieving': 'no',
        },
        prerequisite_quest_ids=('client_of_kourend',),
    ),
    QuestRequirement(
        quest_id='haunted_mine',
        display_name='Haunted Mine',
        direct_skill_requirements={
            'crafting': 35,
        },
        direct_skill_boostability={
            'crafting': 'yes',
        },
        prerequisite_quest_ids=('priest_in_peril',),
    ),
    QuestRequirement(
        quest_id='what_lies_below',
        display_name='What Lies Below',
        direct_skill_requirements={
            'runecraft': 35,
        },
        direct_skill_boostability={
            'runecraft': 'no',
        },
        prerequisite_quest_ids=('rune_mysteries',),
    ),
    QuestRequirement(
        quest_id='tale_of_the_righteous',
        display_name='Tale of the Righteous',
        direct_skill_requirements={
            'strength': 16,
            'mining': 10,
        },
        direct_skill_boostability={
            'strength': 'no',
            'mining': 'no',
        },
        prerequisite_quest_ids=('client_of_kourend',),
    ),
    QuestRequirement(
        quest_id='olafs_quest',
        display_name="Olaf's Quest",
        direct_skill_requirements={
            'firemaking': 40,
            'woodcutting': 50,
        },
        direct_skill_boostability={
            'firemaking': 'yes',
            'woodcutting': 'yes',
        },
        prerequisite_quest_ids=('the_fremennik_trials',),
    ),
    QuestRequirement(
        quest_id='shades_of_mortton',
        display_name="Shades of Mort'ton",
        direct_skill_requirements={
            'crafting': 20,
            'herblore': 15,
            'firemaking': 5,
        },
        direct_skill_boostability={
            'crafting': 'yes',
            'herblore': 'yes',
            'firemaking': 'yes',
        },
        prerequisite_quest_ids=('priest_in_peril',),
    ),
    QuestRequirement(
        quest_id='the_knights_sword',
        display_name="The Knight's Sword",
        direct_skill_requirements={
            'mining': 10,
        },
        direct_skill_boostability={
            'mining': 'yes',
        },
    ),
    QuestRequirement(
        quest_id='tower_of_life',
        display_name='Tower of Life',
        direct_skill_requirements={
            'construction': 10,
        },
        direct_skill_boostability={
            'construction': 'no',
        },
    ),
    QuestRequirement(
        quest_id='mountain_daughter',
        display_name='Mountain Daughter',
        direct_skill_requirements={
            'agility': 20,
        },
        direct_skill_boostability={
            'agility': 'yes',
        },
    ),
    QuestRequirement(
        quest_id='the_garden_of_death',
        display_name='The Garden of Death',
        direct_skill_requirements={
            'farming': 20,
        },
        direct_skill_boostability={
            'farming': 'no',
        },
    ),
    QuestRequirement(
        quest_id='tribal_totem',
        display_name='Tribal Totem',
        direct_skill_requirements={
            'thieving': 21,
        },
        direct_skill_boostability={
            'thieving': 'yes',
        },
    ),
    QuestRequirement(
        quest_id='the_feud',
        display_name='The Feud',
        direct_skill_requirements={
            'thieving': 30,
        },
        direct_skill_boostability={
            'thieving': 'no',
        },
    ),
    QuestRequirement(
        quest_id='the_tourist_trap',
        display_name='The Tourist Trap',
        direct_skill_requirements={
            'fletching': 10,
            'smithing': 20,
        },
        direct_skill_boostability={
            'fletching': 'yes',
            'smithing': 'yes',
        },
    ),
    QuestRequirement(
        quest_id='the_golem',
        display_name='The Golem',
        direct_skill_requirements={
            'crafting': 20,
            'thieving': 25,
        },
        direct_skill_boostability={
            'crafting': 'yes',
            'thieving': 'yes',
        },
    ),
    QuestRequirement(
        quest_id='getting_ahead',
        display_name='Getting Ahead',
        direct_skill_requirements={
            'crafting': 30,
            'construction': 26,
        },
        direct_skill_boostability={
            'crafting': 'no',
            'construction': 'no',
        },
    ),
    QuestRequirement(
        quest_id='the_hand_in_the_sand',
        display_name='The Hand in the Sand',
        direct_skill_requirements={
            'thieving': 17,
            'crafting': 49,
        },
        direct_skill_boostability={
            'thieving': 'no',
            'crafting': 'no',
        },
    ),
    QuestRequirement(
        quest_id="eagles_peak",
        display_name="Eagles' Peak",
        direct_skill_requirements={
            "hunter": 27,
        },
        direct_skill_boostability={
            "hunter": "yes",
        },
    ),
    QuestRequirement(
        quest_id="sea_slug",
        display_name="Sea Slug",
        direct_skill_requirements={
            "firemaking": 30,
        },
        direct_skill_boostability={
            "firemaking": "yes",
        },
    ),
    QuestRequirement(
        quest_id="sleeping_giants",
        display_name="Sleeping Giants",
        direct_skill_requirements={
            "smithing": 15,
        },
        direct_skill_boostability={
            "smithing": "no",
        },
    ),
    QuestRequirement(
        quest_id="fishing_contest",
        display_name="Fishing Contest",
        direct_skill_requirements={
            "fishing": 10,
        },
        direct_skill_boostability={
            "fishing": "no",
        },
    ),
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
        direct_skill_boostability={
            "ranged": "yes",
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
        direct_skill_boostability={
            "crafting": "no",
            "agility": "yes",
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
        direct_skill_boostability={
            "agility": "yes",
            "crafting": "yes",
            "herblore": "yes",
            "magic": "yes",
            "mining": "yes",
            "prayer": "yes",
            "smithing": "yes",
            "strength": "yes",
            "thieving": "yes",
            "woodcutting": "yes",
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
        direct_skill_boostability={
            "crafting": "yes",
            "mining": "yes",
            "smithing": "yes",
            "magic": "yes",
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
        direct_skill_boostability={"cooking": "yes", "fishing": "yes", "herblore": "yes", "mining": "yes"},
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
        direct_skill_boostability={"crafting": "yes", "woodcutting": "yes"},
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
        direct_skill_requirements={
            "herblore": 3,
        },
        direct_skill_boostability={
            "herblore": "yes",
        },
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
            "druidic_ritual",
            "troll_stronghold",
        ),
        direct_skill_boostability={"herblore": "yes"},
    ),
    QuestRequirement(
        quest_id="troll_stronghold",
        display_name="Troll Stronghold",
        direct_skill_requirements={"agility": 15},
        prerequisite_quest_ids=(
            "death_plateau",
        ),
        direct_skill_boostability={"agility": "yes"},
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
        prerequisite_quest_ids=(
            "gertrudes_cat",
        ),
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
        direct_skill_boostability={
            "agility": "yes",
            "cooking": "yes",
        },
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
        direct_skill_boostability={
            "agility": "yes",
            "herblore": "yes",
            "thieving": "yes",
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
        direct_skill_requirements={"agility": 25},
        prerequisite_quest_ids=(
            "nature_spirit",
        ),
        direct_skill_boostability={"agility": "yes"},
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
    QuestRequirement(
        quest_id='meat_and_greet',
        display_name='Meat and Greet',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('children_of_the_sun',),
    ),
    QuestRequirement(
        quest_id='monkey_madness_i',
        display_name='Monkey Madness I',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=('the_grand_tree', 'tree_gnome_village'),
    ),
    QuestRequirement(
        quest_id='royal_trouble',
        display_name='Royal Trouble',
        direct_skill_requirements={'agility': 40, 'slayer': 40},
        direct_skill_boostability={'agility': 'yes', 'slayer': 'yes'},
        prerequisite_quest_ids=('throne_of_miscellania',),
    ),
    QuestRequirement(
        quest_id='scrambled',
        display_name='Scrambled!',
        direct_skill_requirements={'construction': 38, 'cooking': 36, 'smithing': 35},
        direct_skill_boostability={'construction': 'no', 'cooking': 'no', 'smithing': 'no'},
        prerequisite_quest_ids=('children_of_the_sun',),
    ),
    QuestRequirement(
        quest_id='shadow_of_the_storm',
        display_name='Shadow of the Storm',
        direct_skill_requirements={'crafting': 30},
        direct_skill_boostability={'crafting': 'yes'},
        prerequisite_quest_ids=('the_golem', 'demon_slayer'),
    ),
    QuestRequirement(
        quest_id='shadows_of_custodia',
        display_name='Shadows of Custodia',
        direct_skill_requirements={'slayer': 54, 'fishing': 45, 'construction': 41, 'hunter': 36},
        direct_skill_boostability={'slayer': 'no', 'fishing': 'no', 'construction': 'no', 'hunter': 'no'},
        prerequisite_quest_ids=('children_of_the_sun',),
    ),
    QuestRequirement(
        quest_id='the_blood_moon_rises',
        display_name='The Blood Moon Rises',
        direct_skill_requirements={'slayer': 74, 'woodcutting': 74, 'smithing': 72, 'cooking': 72, 'fletching': 70, 'mining': 66, 'hunter': 65, 'crafting': 64, 'herblore': 64, 'magic': 57},
        direct_skill_boostability={'slayer': 'no', 'woodcutting': 'no', 'smithing': 'no', 'cooking': 'no', 'fletching': 'no', 'mining': 'no', 'hunter': 'no', 'crafting': 'no', 'herblore': 'no', 'magic': 'no'},
        prerequisite_quest_ids=('a_night_at_the_theatre', 'sins_of_the_father'),
    ),
    QuestRequirement(
        quest_id='the_final_dawn',
        display_name='The Final Dawn',
        direct_skill_requirements={'thieving': 66, 'runecraft': 52, 'fletching': 52},
        direct_skill_boostability={'thieving': 'no', 'runecraft': 'no', 'fletching': 'no'},
        prerequisite_quest_ids=('the_heart_of_darkness', 'perilous_moons'),
    ),
    QuestRequirement(
        quest_id='the_red_reef',
        display_name='The Red Reef',
        direct_skill_requirements={'sailing': 52, 'smithing': 48},
        direct_skill_boostability={'sailing': 'no', 'smithing': 'no'},
        prerequisite_quest_ids=('troubled_tortugans',),
    ),
    QuestRequirement(
        quest_id='the_ribbiting_tale_of_a_lily_pad_labour_dispute',
        display_name='The Ribbiting Tale of a Lily Pad Labour Dispute',
        direct_skill_requirements={'woodcutting': 15},
        direct_skill_boostability={'woodcutting': 'no'},
        prerequisite_quest_ids=('children_of_the_sun',),
    ),
    QuestRequirement(
        quest_id='x_marks_the_spot',
        display_name='X Marks the Spot',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='the_corsair_curse',
        display_name='The Corsair Curse',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='misthalin_mystery',
        display_name='Misthalin Mystery',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='below_ice_mountain',
        display_name='Below Ice Mountain',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='goblin_diplomacy',
        display_name='Goblin Diplomacy',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='witchs_potion',
        display_name="Witch's Potion",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='black_knights_fortress',
        display_name="Black Knights' Fortress",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='imp_catcher',
        display_name='Imp Catcher',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='sheep_shearer',
        display_name='Sheep Shearer',
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='cooks_assistant',
        display_name="Cook's Assistant",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id="miniquest_alfred_grimhands_barcrawl",
        display_name="Alfred Grimhand's Barcrawl",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id="scorpion_catcher",
        display_name="Scorpion Catcher",
        direct_skill_requirements={"prayer": 31},
        direct_skill_boostability={"prayer": "no"},
        prerequisite_quest_ids=(
            "miniquest_alfred_grimhands_barcrawl",
        ),
    ),
    QuestRequirement(
        quest_id="temple_of_ikov",
        display_name="Temple of Ikov",
        direct_skill_requirements={"thieving": 42},
        direct_skill_boostability={"thieving": "yes"},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id="sheep_herder",
        display_name="Sheep Herder",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id="dwarf_cannon",
        display_name="Dwarf Cannon",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id="murder_mystery",
        display_name="Murder Mystery",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id="death_plateau",
        display_name="Death Plateau",
        direct_skill_requirements={},
        direct_skill_boostability={},
        prerequisite_quest_ids=(),
    ),
    QuestRequirement(
        quest_id='between_a_rock',
        display_name='Between a Rock...',
        direct_skill_requirements={'defence': 30, 'mining': 40, 'smithing': 50},
        prerequisite_quest_ids=(
            'dwarf_cannon',
            'fishing_contest',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={'defence': 'yes', 'mining': 'yes', 'smithing': 'yes'},
        non_skill_conditions=(),
    ),
    QuestRequirement(
        quest_id='creature_of_fenkenstrain',
        display_name='Creature of Fenkenstrain',
        direct_skill_requirements={'crafting': 20, 'thieving': 25},
        prerequisite_quest_ids=(
            'priest_in_peril',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={'crafting': 'yes', 'thieving': 'yes'},
        non_skill_conditions=(
            QuestUnmeasuredCondition(
                quest_id='creature_of_fenkenstrain',
                condition_id='partial_the_restless_ghost',
                condition_kind='PARTIAL_QUEST_PROGRESSION',
                detail='Partial progression through The Restless Ghost is required, including access to a ghostspeak amulet. Full completion is not required.',
                source_wikitext_sha256='a8ee8e00a99b23d4d7d1d48dd4987958d43a3879ecbebb927b44d8a598a9697e',
                evidence_status='NOT_INDEPENDENTLY_MEASURED',
                planning_policy='ASSUMED_FOR_PLANNING_ONLY',
                partial_quest_id='the_restless_ghost',
                alternative_skill_route=None,
            ),
        ),
    ),
    QuestRequirement(
        quest_id='desert_treasure_i',
        display_name='Desert Treasure I',
        direct_skill_requirements={'firemaking': 50, 'magic': 50, 'thieving': 53},
        prerequisite_quest_ids=(
            'the_dig_site',
            'temple_of_ikov',
            'the_tourist_trap',
            'troll_stronghold',
            'priest_in_peril',
            'waterfall_quest',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={'firemaking': 'yes', 'magic': 'no', 'thieving': 'no'},
        non_skill_conditions=(
            QuestUnmeasuredCondition(
                quest_id='desert_treasure_i',
                condition_id='gas_mask_from_plague_city',
                condition_kind='ALTERNATIVE_SKILL_OR_NON_SKILL',
                detail='A gas mask obtained through Plague City is an alternative to unboostable 10 Slayer. Gas-mask possession is not verified by WOM. Plague City is not automatically added as a completed-quest prerequisite.',
                source_wikitext_sha256='510786a8d9ddb4658d6ecfce804d93e3047531e43a5f4948ffabefa6f400dd9a',
                evidence_status='NOT_INDEPENDENTLY_MEASURED',
                planning_policy='ASSUMED_FOR_PLANNING_ONLY',
                partial_quest_id=None,
                alternative_skill_route=(
                    'slayer',
                    10,
                    'no',
                ),
            ),
        ),
    ),
    QuestRequirement(
        quest_id='elemental_workshop_i',
        display_name='Elemental Workshop I',
        direct_skill_requirements={'crafting': 20, 'smithing': 20},
        prerequisite_quest_ids=(),
        access_flags=frozenset({}),
        direct_skill_boostability={'crafting': 'yes', 'smithing': 'yes'},
        non_skill_conditions=(
            QuestUnmeasuredCondition(
                quest_id='elemental_workshop_i',
                condition_id='assisted_elemental_rock_mining',
                condition_kind='ALTERNATIVE_SKILL_OR_NON_SKILL',
                detail='20 Mining (boostable), or the verified alternative: Another player mines the elemental rock, allowing the quest participant to obtain elemental ore without personally meeting 20 Mining. Unmeasured conditions: Another player must mine the elemental rock; Obtain the elemental ore; Complete the required level 35 earth elemental encounter.',
                source_wikitext_sha256='a463af574ffb22a36af46f37f1d1bc0dde48c067041d6c9a64063a3863f009d6',
                evidence_status='NOT_INDEPENDENTLY_MEASURED',
                planning_policy='ASSUMED_FOR_PLANNING_ONLY',
                partial_quest_id=None,
                alternative_skill_route=(
                    'mining',
                    20,
                    'yes',
                ),
            ),
        ),
    ),
    QuestRequirement(
        quest_id='horror_from_the_deep',
        display_name='Horror from the Deep',
        direct_skill_requirements={'agility': 35},
        prerequisite_quest_ids=(
            'miniquest_alfred_grimhands_barcrawl',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={'agility': 'yes'},
        non_skill_conditions=(),
    ),
    QuestRequirement(
        quest_id='recruitment_drive',
        display_name='Recruitment Drive',
        direct_skill_requirements={},
        prerequisite_quest_ids=(
            'black_knights_fortress',
            'druidic_ritual',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={},
        non_skill_conditions=(),
    ),
    QuestRequirement(
        quest_id='roving_elves',
        display_name='Roving Elves',
        direct_skill_requirements={},
        prerequisite_quest_ids=(
            'regicide',
            'waterfall_quest',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={},
        non_skill_conditions=(
            QuestUnmeasuredCondition(
                quest_id='roving_elves',
                condition_id='charter_ship_to_elven_woods',
                condition_kind='ALTERNATIVE_SKILL_OR_NON_SKILL',
                detail='Charter-ship travel is an alternative to the direct 56 Agility travel requirement. All inherited Regicide requirements remain.',
                source_wikitext_sha256='8a9f7b5e4201b0527743c67f21dce046040213edab78a8e2fb41f1d320865d25',
                evidence_status='NOT_INDEPENDENTLY_MEASURED',
                planning_policy='ASSUMED_FOR_PLANNING_ONLY',
                partial_quest_id=None,
                alternative_skill_route=(
                    'agility',
                    56,
                    'yes',
                ),
            ),
        ),
    ),
    QuestRequirement(
        quest_id='tai_bwo_wannai_trio',
        display_name='Tai Bwo Wannai Trio',
        direct_skill_requirements={'agility': 15, 'cooking': 30, 'fishing': 5},
        prerequisite_quest_ids=(
            'jungle_potion',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={'agility': 'yes', 'cooking': 'no', 'fishing': 'yes'},
        non_skill_conditions=(),
    ),
    QuestRequirement(
        quest_id='tears_of_guthix',
        display_name='Tears of Guthix',
        direct_skill_requirements={'crafting': 20, 'firemaking': 49, 'mining': 20},
        prerequisite_quest_ids=(),
        access_flags=frozenset({}),
        direct_skill_boostability={'crafting': 'yes', 'firemaking': 'yes', 'mining': 'yes'},
        non_skill_conditions=(),
    ),
    QuestRequirement(
        quest_id='the_lost_tribe',
        display_name='The Lost Tribe',
        direct_skill_requirements={'agility': 13, 'mining': 17, 'thieving': 13},
        prerequisite_quest_ids=(
            'goblin_diplomacy',
            'rune_mysteries',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={'agility': 'yes', 'mining': 'yes', 'thieving': 'yes'},
        non_skill_conditions=(),
    ),
    QuestRequirement(
        quest_id='garden_of_tranquillity',
        display_name='Garden of Tranquillity',
        direct_skill_requirements={'farming': 25},
        prerequisite_quest_ids=(
            'creature_of_fenkenstrain',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={'farming': 'no'},
        non_skill_conditions=(),
    ),
    QuestRequirement(
        quest_id='mournings_end_part_i',
        display_name="Mourning's End Part I",
        direct_skill_requirements={'ranged': 60, 'thieving': 50},
        prerequisite_quest_ids=(
            'roving_elves',
            'big_chompy_bird_hunting',
            'sheep_herder',
        ),
        access_flags=frozenset({}),
        direct_skill_boostability={'ranged': 'no', 'thieving': 'no'},
        non_skill_conditions=(),
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
