from utils.board_generation import RouteMode, TileCategory
from utils.osrs_composite_tile_catalogue import (
    get_curated_composite_tile_candidates,
)


def test_curated_composite_tile_candidates_include_skilling_minigame_sampler():
    candidates = get_curated_composite_tile_candidates()

    assert len(
        candidates
    ) == 1

    candidate = candidates[0]

    assert candidate.title == "Skilling minigame sampler"
    assert candidate.primary_category == TileCategory.HYBRID
    assert candidate.route_mode == RouteMode.N_OF
    assert candidate.required_route_count == 2
    assert len(
        candidate.routes
    ) == 3
    assert tuple(
        route.display_text
        for route in candidate.routes
    ) == (
        "Complete 100 Guardians of the Rift completions",
        "Complete 100 Tempoross completions",
        "Complete 100 Wintertodt kills",
    )


def test_curated_composite_tile_candidates_expose_internal_hard_tags():
    candidate = get_curated_composite_tile_candidates()[0]

    assert "activity_group:skilling_minigames" in candidate.all_hard_unique_tags
    assert "component:guardians_of_the_rift_completions_metric" in candidate.all_hard_unique_tags
    assert "component:tempoross_completions_metric" in candidate.all_hard_unique_tags
    assert "component:wintertodt_kills_metric" in candidate.all_hard_unique_tags
    assert "metric:guardians_of_the_rift" in candidate.all_hard_unique_tags
    assert "metric:tempoross" in candidate.all_hard_unique_tags
    assert "metric:wintertodt" in candidate.all_hard_unique_tags
