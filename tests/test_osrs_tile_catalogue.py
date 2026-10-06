from utils.osrs_pets import get_osrs_pet_options
from utils.osrs_tile_template_expansion import (
    STATIC_DROP_TEMPLATES,
    STATIC_KILLCOUNT_TEMPLATES,
    STATIC_METRIC_TEMPLATES,
)

from utils.board_generation import (
    PetRole,
    RouteMode,
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
            "component:vorki_pet",
            "metric:pet_vorki",
            "pet:vorki",
            "source:vorkath",
        }
    )

    snakeling_tile = candidates["Obtain Pet snakeling"]

    assert snakeling_tile.all_hard_unique_tags == frozenset(
        {
            "component:pet_snakeling_pet",
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

    from utils.osrs_generated_drop_tile_candidates import (
        build_generated_drop_tile_candidates,
    )

    expected_drop_candidates = build_generated_drop_tile_candidates()

    def signature(candidate):
        route = candidate.routes[0]
        return (
            candidate.title,
            candidate.point_value,
            route.drop_group_id,
            route.drop_id,
            route.target,
        )

    assert len(drop_candidates) == len(expected_drop_candidates)
    assert {
        signature(candidate)
        for candidate in drop_candidates
    } == {
        signature(candidate)
        for candidate in expected_drop_candidates
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


def test_curated_tile_generation_candidates_expand_metric_templates():
    candidates = get_curated_tile_generation_candidates()

    metric_candidates = [
        candidate
        for candidate in candidates
        if (
            candidate.primary_category == TileCategory.HYBRID
            and candidate.route_mode == RouteMode.SINGLE
            and candidate.routes[0].tracking_source == TrackingSource.WOM
        )
    ]

    assert len(metric_candidates) == len(STATIC_METRIC_TEMPLATES) * 5

    assert {
        candidate.point_value
        for candidate in metric_candidates
    } == {
        1,
        2,
        3,
        4,
        5,
    }

    assert {
        candidate.title
        for candidate in metric_candidates
    } >= {
        "Complete 25 Guardians of the Rift completions",
        "Complete 50 medium-or-harder clue scrolls",
    }


def test_curated_tile_generation_board_limits_clue_tiles_by_hard_tag():
    from utils.board_generation import assemble_board_candidates

    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    clue_tiles = [
        candidate
        for candidate in board.candidates
        if "activity_group:clue_scrolls" in candidate.all_hard_unique_tags
    ]

    assert len(clue_tiles) <= 1


def test_pet_candidate_from_option_expands_via_component_single_recipe():
    from utils.board_generation import (
        PetRole,
        TileCategory,
        TrackingSource,
    )
    from utils.osrs_tile_catalogue import (
        make_pet_candidate_from_option,
    )

    candidate = make_pet_candidate_from_option(
        {
            "label": "Vorkath - Vorki",
            "value": "Vorki",
        }
    )
    route = candidate.routes[0]

    assert candidate.title == "Obtain Vorki"
    assert candidate.point_value == 5
    assert candidate.primary_category == TileCategory.PET
    assert candidate.pet_role == PetRole.PRIMARY
    assert candidate.rng_level == 4
    assert route.display_text == "Obtain Vorki"
    assert route.target == 1
    assert route.tracking_source == TrackingSource.DINK
    assert route.metric_id == "pet_vorki"
    assert route.source_id == "vorkath"
    assert route.pet_id == "vorki"
    assert candidate.explanation == (
        "Generated specific pet candidate from the OSRS pet option list.",
    )
    assert "component:vorki_pet" in candidate.all_hard_unique_tags
    assert "metric:pet_vorki" in candidate.all_hard_unique_tags
    assert "source:vorkath" in candidate.all_hard_unique_tags
    assert "pet:vorki" in candidate.all_hard_unique_tags


def test_curated_tile_generation_candidates_use_common_validation(monkeypatch):
    import utils.osrs_tile_catalogue as catalogue

    captured = {}

    def fake_validate(candidates):
        captured["candidate_count"] = len(
            candidates
        )
        return tuple(
            candidates
        )

    monkeypatch.setattr(
        catalogue,
        "assert_valid_tile_candidate_pool",
        fake_validate,
    )

    candidates = catalogue.get_curated_tile_generation_candidates()

    assert captured["candidate_count"] == len(
        candidates
    )
    assert captured["candidate_count"] > 25


def test_curated_tile_generation_candidates_include_composite_candidates():
    from utils.board_generation import RouteMode
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates

    candidates = {
        candidate.title: candidate
        for candidate in get_curated_tile_generation_candidates()
    }

    candidate = candidates["Skilling minigame sampler"]

    assert candidate.route_mode == RouteMode.N_OF
    assert candidate.required_route_count == 2
    assert len(
        candidate.routes
    ) == 3
    assert "activity_group:skilling_minigames" in candidate.all_hard_unique_tags
    assert "component:guardians_of_the_rift_completions_metric" in candidate.all_hard_unique_tags
    assert "component:tempoross_completions_metric" in candidate.all_hard_unique_tags
    assert "component:wintertodt_kills_metric" in candidate.all_hard_unique_tags


def test_curated_tile_generation_candidates_do_not_include_targets_above_defined_group_size():
    from utils.osrs_drop_groups import get_max_distinct_drop_count
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates

    max_count = get_max_distinct_drop_count(
        "dagannoth_rex_uniques"
    )

    assert max_count >= 2

    targets = {
        candidate.routes[0].target
        for candidate in get_curated_tile_generation_candidates()
        if (
            candidate.primary_category == TileCategory.DROP
            and candidate.routes[0].drop_group_id == "dagannoth_rex_uniques"
            and candidate.routes[0].drop_id is None
        )
    }

    assert set(
        range(
            1,
            max_count + 1,
        )
    ).issubset(targets)
    assert all(
        target <= max_count
        for target in targets
    )

def test_generated_board_does_not_include_overlapping_wilderness_drop_groups():
    from utils.board_generation import assemble_board_candidates
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates

    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    selected_drop_group_tags = {
        tag
        for candidate in board.candidates
        for tag in candidate.all_hard_unique_tags
        if tag.startswith(
            "drop_group:"
        )
    }

    assert not {
        "drop_group:wilderness_unique",
        "drop_group:wilderness_ring",
    }.issubset(
        selected_drop_group_tags
    )


def test_generated_board_respects_wilderness_pvm_mix_rules():
    from utils.board_generation import (
        assemble_board_candidates,
        candidate_has_wilderness_drop_route,
        candidate_has_wilderness_killcount_route,
    )
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates

    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    wilderness_drop_count = sum(
        1
        for candidate in board.candidates
        if candidate_has_wilderness_drop_route(
            candidate
        )
    )
    wilderness_killcount_count = sum(
        1
        for candidate in board.candidates
        if candidate_has_wilderness_killcount_route(
            candidate
        )
    )

    assert wilderness_killcount_count <= 2
    assert not (
        wilderness_drop_count
        and wilderness_killcount_count
    )


def test_curated_tile_generation_board_uses_one_primary_pet_tile_by_default():
    from utils.board_generation import PetRole, assemble_board_candidates
    from utils.osrs_tile_catalogue import get_curated_tile_generation_candidates

    board = assemble_board_candidates(
        get_curated_tile_generation_candidates()
    )

    primary_pet_tiles = [
        candidate
        for candidate in board.candidates
        if candidate.pet_role == PetRole.PRIMARY
    ]

    assert len(primary_pet_tiles) == 1
