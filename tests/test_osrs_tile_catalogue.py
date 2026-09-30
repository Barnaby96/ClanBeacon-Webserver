from utils.osrs_pets import get_osrs_pet_options
from utils.osrs_tile_template_expansion import (
    STATIC_DROP_TEMPLATES,
    STATIC_KILLCOUNT_TEMPLATES,
)

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
    get_curated_tile_generation_candidates,
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

    assert {
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
    }.issubset(titles)

    assert "Obtain any pet" not in titles
    assert "Obtain any skilling pet" not in titles


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


def test_curated_catalogue_contains_specific_primary_pet_tiles_for_all_pet_options():
    pet_candidates = [
        candidate
        for candidate in get_curated_tile_candidates()
        if candidate.primary_category == TileCategory.PET
    ]

    pet_options = get_osrs_pet_options()
    expected_pet_titles = {
        f"Obtain {option['value']}"
        for option in pet_options
    }

    assert {
        candidate.title
        for candidate in pet_candidates
    } == expected_pet_titles

    assert len(pet_candidates) == len(pet_options)
    assert all(
        candidate.pet_role == PetRole.PRIMARY
        for candidate in pet_candidates
    )
    assert all(
        candidate.routes[0].tracking_source == TrackingSource.DINK
        for candidate in pet_candidates
    )


def test_specific_pet_candidates_use_pet_and_source_tags():
    candidates = {
        candidate.title: candidate
        for candidate in get_curated_tile_candidates()
    }

    vorki_tile = candidates["Obtain Vorki"]

    assert vorki_tile.all_hard_unique_tags == frozenset(
        {
            "metric:pet_vorki",
            "pet:vorki",
            "source:vorkath",
        }
    )

    snakeling_tile = candidates["Obtain Pet snakeling"]

    assert snakeling_tile.all_hard_unique_tags == frozenset(
        {
            "metric:pet_pet_snakeling",
            "pet:pet_snakeling",
            "source:zulrah",
        }
    )


def test_specific_pet_candidates_conflict_with_matching_secondary_pet_routes():
    candidates = {
        candidate.title: candidate
        for candidate in get_curated_tile_candidates()
    }

    rocky_primary_tile = candidates["Obtain Rocky"]
    rocky_secondary_route_tile = candidates[
        "Gain 1,000,000 Thieving XP OR obtain Rocky"
    ]

    assert "pet:rocky" in rocky_primary_tile.all_hard_unique_tags
    assert "pet:rocky" in rocky_secondary_route_tile.all_hard_unique_tags
    assert "source:thieving" in rocky_primary_tile.all_hard_unique_tags
    assert "source:thieving" in rocky_secondary_route_tile.all_hard_unique_tags


def test_curated_tile_generation_candidates_expand_killcount_templates():
    candidates = get_curated_tile_generation_candidates()

    killcount_candidates = [
        candidate
        for candidate in candidates
        if candidate.primary_category == TileCategory.KILLCOUNT
    ]

    assert len(killcount_candidates) == len(STATIC_KILLCOUNT_TEMPLATES) * 5

    assert {
        candidate.point_value
        for candidate in killcount_candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }

    assert {
        candidate.title
        for candidate in killcount_candidates
    } >= {
        "Complete 50 Zulrah KC",
        "Complete 400 Zulrah KC",
        "Complete 25 Vorkath KC",
        "Complete 400 Vorkath KC",
        "Complete 25 Giant Mole KC",
        "Complete 500 Scurrius KC",
    }


def test_curated_tile_generation_candidates_expand_drop_templates():
    candidates = get_curated_tile_generation_candidates()

    drop_candidates = [
        candidate
        for candidate in candidates
        if candidate.primary_category == TileCategory.DROP
    ]

    assert len(drop_candidates) == len(STATIC_DROP_TEMPLATES) * 5

    assert {
        candidate.point_value
        for candidate in drop_candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }

    assert {
        candidate.title
        for candidate in drop_candidates
    } >= {
        "Obtain 1 Zulrah unique",
        "Obtain 5 Zulrah uniques",
        "Obtain 1 Vorkath unique",
        "Obtain 5 Vorkath uniques",
        "Obtain 1 Giant Mole unique",
        "Obtain 5 Scurrius uniques",
    }


def test_curated_tile_generation_candidates_expand_skill_xp_templates():
    candidates = get_curated_tile_generation_candidates()

    skill_candidates = [
        candidate
        for candidate in candidates
        if candidate.primary_category == TileCategory.SKILL
    ]

    assert len(skill_candidates) >= 50

    assert {
        candidate.point_value
        for candidate in skill_candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }

    assert {
        candidate.title
        for candidate in skill_candidates
    } >= {
        "Gain 250,000 Cooking XP",
        "Gain 1,500,000 Cooking XP",
        "Gain 250,000 Hunter XP",
        "Gain 1,500,000 Hunter XP",
    }


def test_curated_tile_generation_candidates_can_assemble_default_board():
    from utils.board_generation import assemble_board_candidates

    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    assert len(board.candidates) == 25
    assert {
        candidate.point_value
        for candidate in board.candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }
