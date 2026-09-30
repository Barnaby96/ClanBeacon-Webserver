import pytest

from utils.board_generation import (
    TileCategory,
    TrackingSource,
)
from utils.osrs_tile_component_catalogue import get_curated_tile_components
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)
from utils.osrs_tile_component_selection import (
    ComponentSelectionCriteria,
    component_matches_criteria,
    require_component_count,
    select_components,
)


def make_component(
    component_id,
    component_type,
    tracking_source=TrackingSource.WOM,
    groups=(),
    compatible_recipe_ids=("SINGLE",),
):
    return TileComponent(
        component_id=component_id,
        component_type=component_type,
        display_name=component_id,
        tracking_source=tracking_source,
        target_model_id="Static",
        boss_id=component_id
        if component_type == TileComponentType.KILLCOUNT
        else None,
        skill_id=component_id
        if component_type == TileComponentType.EXPERIENCE
        else None,
        metric_id=component_id
        if component_type == TileComponentType.WOM_METRIC
        else None,
        groups=groups,
        compatible_recipe_ids=compatible_recipe_ids,
    )


def test_component_selection_criteria_normalises_inputs():
    criteria = ComponentSelectionCriteria(
        component_types={
            TileComponentType.KILLCOUNT,
        },
        primary_categories={
            TileCategory.KILLCOUNT,
        },
        tracking_sources={
            TrackingSource.WOM,
        },
        any_groups={
            "Wilderness Bosses",
        },
        supported_recipe_ids={
            "single",
        },
    )

    assert criteria.component_types == frozenset(
        {
            "KILLCOUNT",
        }
    )
    assert criteria.primary_categories == frozenset(
        {
            "KILLCOUNT",
        }
    )
    assert criteria.tracking_sources == frozenset(
        {
            "WOM",
        }
    )
    assert criteria.any_groups == frozenset(
        {
            "wilderness_bosses",
        }
    )
    assert criteria.supported_recipe_ids == frozenset(
        {
            "SINGLE",
        }
    )


def test_component_matches_criteria_checks_type_group_and_recipe():
    component = make_component(
        "Callisto",
        TileComponentType.KILLCOUNT,
        groups=(
            "Wilderness Bosses",
        ),
        compatible_recipe_ids=(
            "SINGLE",
            "N_OF",
        ),
    )

    criteria = ComponentSelectionCriteria(
        component_types={
            TileComponentType.KILLCOUNT,
        },
        any_groups={
            "wilderness_bosses",
        },
        supported_recipe_ids={
            "N_OF",
        },
    )

    assert component_matches_criteria(
        component,
        criteria,
    )


def test_component_matches_criteria_rejects_wrong_group():
    component = make_component(
        "Callisto",
        TileComponentType.KILLCOUNT,
        groups=(
            "Wilderness Bosses",
        ),
    )

    criteria = ComponentSelectionCriteria(
        any_groups={
            "god_wars",
        },
    )

    assert not component_matches_criteria(
        component,
        criteria,
    )


def test_select_components_filters_component_pool():
    callisto = make_component(
        "Callisto",
        TileComponentType.KILLCOUNT,
        groups=(
            "Wilderness Bosses",
        ),
    )
    magic = make_component(
        "Magic",
        TileComponentType.EXPERIENCE,
        groups=(
            "Combat Skills",
        ),
    )

    selected = select_components(
        (
            callisto,
            magic,
        ),
        ComponentSelectionCriteria(
            component_types={
                TileComponentType.KILLCOUNT,
            },
        ),
    )

    assert selected == (
        callisto,
    )


def test_select_components_supports_include_and_exclude_ids():
    callisto = make_component(
        "Callisto",
        TileComponentType.KILLCOUNT,
    )
    venenatis = make_component(
        "Venenatis",
        TileComponentType.KILLCOUNT,
    )

    selected = select_components(
        (
            callisto,
            venenatis,
        ),
        ComponentSelectionCriteria(
            include_component_ids={
                "Callisto",
                "Venenatis",
            },
            exclude_component_ids={
                "Callisto",
            },
        ),
    )

    assert selected == (
        venenatis,
    )


def test_require_component_count_rejects_insufficient_components():
    with pytest.raises(
        ValueError,
        match="Need at least 2 wilderness bosses; found 1",
    ):
        require_component_count(
            (
                object(),
            ),
            2,
            label="wilderness bosses",
        )


def test_curated_component_pool_can_be_selected_by_type():
    components = get_curated_tile_components()

    pet_components = select_components(
        components,
        ComponentSelectionCriteria(
            component_types={
                TileComponentType.PET,
            },
        ),
    )
    wom_components = select_components(
        components,
        ComponentSelectionCriteria(
            tracking_sources={
                TrackingSource.WOM,
            },
        ),
    )
    clue_components = select_components(
        components,
        ComponentSelectionCriteria(
            any_groups={
                "clue_scrolls",
            },
        ),
    )

    assert len(
        pet_components
    ) == 71
    assert len(
        wom_components
    ) == 40
    assert tuple(
        component.component_id
        for component in clue_components
    ) == (
        "clue_scrolls_medium_plus_completed_metric",
        "clue_scrolls_hard_completed_metric",
        "clue_scrolls_elite_completed_metric",
    )
