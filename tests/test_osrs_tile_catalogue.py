from utils.board_generation import (
    PetRole,
    TileCategory,
    TrackingSource,
)
from utils.osrs_tile_catalogue import (
    get_curated_drop_led_candidates,
    get_curated_killcount_led_candidates,
    get_curated_skill_led_candidates,
    get_curated_tile_candidates,
)


def test_curated_tile_candidate_titles_are_unique():
    titles = [
        candidate.title
        for candidate in get_curated_tile_candidates()
    ]

    assert len(titles) == len(set(titles))


def test_curated_catalogue_contains_expected_initial_candidates():
    titles = {
        candidate.title
        for candidate in get_curated_tile_candidates()
    }

    assert titles == {
        "Obtain any skilling pet",
        "Obtain any pet",
        "Gain 500,000 Cooking XP",
        "Gain 500,000 Firemaking XP",
        "Gain 750,000 Fletching XP",
        "Gain 750,000 Crafting XP",
        "Complete 150 Zulrah KC",
        "Obtain any Zulrah unique",
        "Complete 150 Vorkath KC",
        "Obtain any Vorkath unique",
        "Gain 1,000,000 Thieving XP OR obtain Rocky",
        "Gain 1,000,000 Fishing XP OR obtain Heron",
        "Gain 1,000,000 Mining XP OR obtain Rock golem",
        "Gain 1,000,000 Runecraft XP OR obtain Rift guardian",
    }


def test_curated_killcount_candidates_are_wom_tracked():
    candidates = get_curated_killcount_led_candidates()

    assert {
        candidate.title
        for candidate in candidates
    } == {
        "Complete 150 Zulrah KC",
        "Complete 150 Vorkath KC",
    }

    for candidate in candidates:
        assert candidate.primary_category == TileCategory.KILLCOUNT
        assert candidate.routes[0].tracking_source == TrackingSource.WOM


def test_curated_drop_candidates_are_dink_tracked():
    candidates = get_curated_drop_led_candidates()

    assert {
        candidate.title
        for candidate in candidates
    } == {
        "Obtain any Zulrah unique",
        "Obtain any Vorkath unique",
    }

    for candidate in candidates:
        assert candidate.primary_category == TileCategory.DROP
        assert candidate.routes[0].tracking_source == TrackingSource.DINK


def test_curated_skill_candidates_include_plain_xp_and_secondary_pet_routes():
    candidates = get_curated_skill_led_candidates()

    assert len(candidates) == 8

    plain_skill_candidates = [
        candidate
        for candidate in candidates
        if candidate.pet_role == PetRole.NONE
    ]
    secondary_pet_candidates = [
        candidate
        for candidate in candidates
        if candidate.pet_role == PetRole.SECONDARY
    ]

    assert {
        candidate.title
        for candidate in plain_skill_candidates
    } == {
        "Gain 500,000 Cooking XP",
        "Gain 500,000 Firemaking XP",
        "Gain 750,000 Fletching XP",
        "Gain 750,000 Crafting XP",
    }

    assert len(secondary_pet_candidates) == 4

    for candidate in plain_skill_candidates:
        assert candidate.primary_category == TileCategory.SKILL
        assert candidate.routes[0].tracking_source == TrackingSource.WOM

    for candidate in secondary_pet_candidates:
        assert candidate.primary_category == TileCategory.SKILL
        assert candidate.secondary_categories == frozenset(
            {
                TileCategory.PET
            }
        )
        assert candidate.routes[0].tracking_source == TrackingSource.WOM
        assert candidate.routes[1].tracking_source == TrackingSource.DINK


def test_zulrah_catalogue_candidates_use_regicide_access_profile():
    candidates = {
        candidate.title: candidate
        for candidate in get_curated_tile_candidates()
    }

    for title in (
        "Complete 150 Zulrah KC",
        "Obtain any Zulrah unique",
    ):
        assert candidates[title].access_profile.effective_skill_requirements == {
            "agility": 56,
            "ranged": 25,
            "crafting": 10,
        }


def test_vorkath_catalogue_candidates_use_dragon_slayer_ii_access_profile():
    candidates = {
        candidate.title: candidate
        for candidate in get_curated_tile_candidates()
    }

    for title in (
        "Complete 150 Vorkath KC",
        "Obtain any Vorkath unique",
    ):
        assert candidates[title].access_profile.effective_skill_requirements == {
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


def test_catalogue_alternatives_can_share_source_tags_before_board_assembly():
    candidates = {
        candidate.title: candidate
        for candidate in get_curated_tile_candidates()
    }

    zulrah_kc = candidates["Complete 150 Zulrah KC"]
    zulrah_drop = candidates["Obtain any Zulrah unique"]

    assert "source:zulrah" in zulrah_kc.all_hard_unique_tags
    assert "source:zulrah" in zulrah_drop.all_hard_unique_tags


def test_curated_catalogue_contains_primary_pet_tiles():
    pet_candidates = [
        candidate
        for candidate in get_curated_tile_candidates()
        if candidate.primary_category == TileCategory.PET
    ]

    assert {
        candidate.title
        for candidate in pet_candidates
    } == {
        "Obtain any skilling pet",
        "Obtain any pet",
    }

    assert all(
        candidate.pet_role == PetRole.PRIMARY
        for candidate in pet_candidates
    )
    assert all(
        candidate.routes[0].tracking_source == TrackingSource.DINK
        for candidate in pet_candidates
    )

    broad_pet_tile = {
        candidate.title: candidate
        for candidate in pet_candidates
    }["Obtain any pet"]

    assert broad_pet_tile.all_hard_unique_tags == frozenset(
        {
            "metric:pet_group_any_pet",
            "source:any_pet",
            "pet_group:any_pet",
        }
    )
