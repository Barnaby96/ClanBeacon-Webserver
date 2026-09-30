from utils.board_generation import (
    RouteMode,
    TileCategory,
    TrackingSource,
)
from utils.osrs_generation_recipes import StaticPointTargetModel
from utils.osrs_tile_component_expansion import (
    SingleComponentExpansion,
    expand_single_component,
)
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)


def make_callisto_component():
    return TileComponent(
        component_id="Callisto KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Callisto",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        source_id="Callisto",
        boss_id="Callisto",
        notes=(
            "Component note.",
        ),
    )


def test_expand_single_component_builds_candidates_for_each_target():
    component = make_callisto_component()
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            1: 10,
            3: 35,
        },
    )

    candidates = expand_single_component(
        component=component,
        target_model=target_model,
        title_formatter=lambda point_value, target: (
            f"Complete {target} Callisto KC"
        ),
        explanation_formatter=lambda point_value, target: (
            f"Generated {point_value}-point Callisto target.",
        ),
    )

    assert len(
        candidates
    ) == 2

    first_candidate = candidates[0]
    second_candidate = candidates[1]

    assert first_candidate.title == "Complete 10 Callisto KC"
    assert first_candidate.point_value == 1
    assert first_candidate.primary_category == TileCategory.KILLCOUNT
    assert first_candidate.route_mode == RouteMode.SINGLE
    assert first_candidate.explanation == (
        "Component note.",
        "Generated 1-point Callisto target.",
    )

    assert second_candidate.title == "Complete 35 Callisto KC"
    assert second_candidate.point_value == 3
    assert second_candidate.routes[0].target == 35


def test_expand_single_component_can_use_separate_display_text_formatter():
    component = make_callisto_component()
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            2: 25,
        },
    )

    candidate = expand_single_component(
        component=component,
        target_model=target_model,
        title_formatter=lambda point_value, target: "Callisto challenge",
        display_text_formatter=lambda point_value, target: (
            f"Complete {target} Callisto KC"
        ),
    )[0]

    assert candidate.title == "Callisto challenge"
    assert candidate.routes[0].display_text == "Complete 25 Callisto KC"


def test_single_component_expansion_dataclass_delegates_to_helper():
    component = make_callisto_component()
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            4: 50,
        },
    )

    expansion = SingleComponentExpansion(
        component=component,
        target_model=target_model,
        title_formatter=lambda point_value, target: (
            f"Complete {target} Callisto KC"
        ),
        display_text_formatter=lambda point_value, target: (
            f"Complete {target} Callisto KC"
        ),
        explanation_formatter=lambda point_value, target: (
            f"Generated {point_value}-point Callisto target.",
        ),
    )

    candidate = expansion.expand()[0]

    assert candidate.title == "Complete 50 Callisto KC"
    assert candidate.point_value == 4
    assert candidate.routes[0].target == 50
    assert candidate.explanation == (
        "Component note.",
        "Generated 4-point Callisto target.",
    )
