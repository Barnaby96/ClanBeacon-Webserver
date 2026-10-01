import pytest

from utils.board_generation import RouteMode, TileCategory
from utils.osrs_metric_n_of_recipes import (
    build_skilling_minigame_sampler_candidate,
    build_wom_metric_group_n_of_candidate,
    get_static_metric_target_models_by_component_id,
    select_wom_metric_components_for_group,
)
from utils.osrs_tile_component_catalogue import get_static_metric_components


def test_select_wom_metric_components_for_group_finds_skilling_minigames():
    selected = select_wom_metric_components_for_group(
        get_static_metric_components(),
        "skilling_minigames",
    )

    assert tuple(
        component.component_id
        for component in selected
    ) == (
        "guardians_of_the_rift_completions_metric",
        "tempoross_completions_metric",
        "wintertodt_kills_metric",
    )


def test_static_metric_target_models_are_keyed_by_component_id():
    target_models = get_static_metric_target_models_by_component_id()

    assert target_models[
        "guardians_of_the_rift_completions_metric"
    ].target_for_point_value(
        3
    ) == 100
    assert target_models[
        "tempoross_completions_metric"
    ].target_for_point_value(
        3
    ) == 100
    assert target_models[
        "wintertodt_kills_metric"
    ].target_for_point_value(
        3
    ) == 100


def test_build_skilling_minigame_sampler_candidate():
    candidate = build_skilling_minigame_sampler_candidate(
        point_value=3,
        required_route_count=2,
    )

    assert candidate.title == "Skilling minigame sampler"
    assert candidate.point_value == 3
    assert candidate.primary_category == TileCategory.HYBRID
    assert candidate.route_mode == RouteMode.N_OF
    assert candidate.required_route_count == 2
    assert len(candidate.routes) == 3
    assert tuple(
        route.display_text
        for route in candidate.routes
    ) == (
        "Complete 100 Guardians of the Rift completions",
        "Complete 100 Tempoross completions",
        "Complete 100 Wintertodt kills",
    )
    assert candidate.explanation == (
        "Generated from WOM metric components in the skilling_minigames group.",
        "Generated 3-point N_OF tile requiring 2 of 3 routes.",
    )
    assert "activity_group:skilling_minigames" in candidate.all_hard_unique_tags
    assert "component:guardians_of_the_rift_completions_metric" in candidate.all_hard_unique_tags
    assert "component:tempoross_completions_metric" in candidate.all_hard_unique_tags
    assert "component:wintertodt_kills_metric" in candidate.all_hard_unique_tags


def test_build_wom_metric_group_n_of_candidate_rejects_insufficient_components():
    with pytest.raises(
        ValueError,
        match="Need at least 2 missing_group components; found 0",
    ):
        build_wom_metric_group_n_of_candidate(
            components=get_static_metric_components(),
            target_model_by_component_id=get_static_metric_target_models_by_component_id(),
            group_id="missing_group",
            point_value=3,
            required_route_count=2,
            title="Missing group",
        )
