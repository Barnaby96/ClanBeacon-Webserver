import pytest

from utils.board_generation import (
    AccessFlag,
    AccessProfile,
    RouteMode,
    TileCategory,
    TrackingSource,
)
from utils.osrs_generation_recipes import (
    StaticPointTargetModel,
    build_single_tile_candidate,
)
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)


def test_static_point_target_model_normalises_targets():
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            3: 35,
            1: 10,
        },
    )

    assert target_model.target_model_id == "static_kc"
    assert target_model.target_by_point_value == (
        (1, 10),
        (3, 35),
    )
    assert target_model.target_for_point_value(3) == 35


def test_static_point_target_model_rejects_missing_point_value():
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            1: 10,
        },
    )

    with pytest.raises(
        ValueError,
        match="No target for 3-point tiles",
    ):
        target_model.target_for_point_value(
            3
        )


def test_build_single_killcount_candidate_from_component():
    access_profile = AccessProfile(
        effective_skill_requirements={
            "attack": 70,
        },
        access_flags=frozenset(
            {
                AccessFlag.QUEST_LOCKED,
            }
        ),
    )
    component = TileComponent(
        component_id="Callisto KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Callisto",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        source_id="Callisto",
        boss_id="Callisto",
        groups=(
            "Wilderness Bosses",
        ),
        access_profile=access_profile,
        rng_level=1,
        notes=(
            "Prototype component note.",
        ),
    )
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            3: 35,
        },
    )

    candidate = build_single_tile_candidate(
        component,
        3,
        target_model,
    )

    assert candidate.title == "Complete 35 Callisto KC"
    assert candidate.point_value == 3
    assert candidate.primary_category == TileCategory.KILLCOUNT
    assert candidate.route_mode == RouteMode.SINGLE
    assert candidate.rng_level == 1
    assert candidate.access_profile is access_profile
    assert candidate.explanation == (
        "Prototype component note.",
        "Generated 3-point SINGLE tile from component callisto_kc.",
    )

    route = candidate.routes[0]

    assert route.display_text == "Complete 35 Callisto KC"
    assert route.target == 35
    assert route.tracking_source == TrackingSource.WOM
    assert route.metric_id == "boss_callisto_kc"
    assert route.source_id == "callisto"
    assert route.boss_id == "callisto"

    assert {
        "component:callisto_kc",
        "source:callisto",
        "boss:callisto",
        "activity_group:wilderness_bosses",
    }.issubset(
        candidate.all_hard_unique_tags
    )


def test_build_single_candidate_accepts_custom_title_and_display_text():
    component = TileComponent(
        component_id="Venenatis KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Venenatis",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        source_id="Venenatis",
        boss_id="Venenatis",
    )
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            2: 25,
        },
    )

    candidate = build_single_tile_candidate(
        component,
        2,
        target_model,
        title="Spider stomper",
        display_text="Complete 25 Venenatis KC",
    )

    assert candidate.title == "Spider stomper"
    assert candidate.routes[0].display_text == "Complete 25 Venenatis KC"


def test_build_single_candidate_rejects_recipe_incompatible_component():
    component = TileComponent(
        component_id="Callisto KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Callisto",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        source_id="Callisto",
        boss_id="Callisto",
        compatible_recipe_ids=(
            "N_OF",
        ),
    )
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            3: 35,
        },
    )

    with pytest.raises(
        ValueError,
        match="does not support",
    ):
        build_single_tile_candidate(
            component,
            3,
            target_model,
        )


def test_build_single_candidate_rejects_target_model_mismatch():
    component = TileComponent(
        component_id="Callisto KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Callisto",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        source_id="Callisto",
        boss_id="Callisto",
    )
    target_model = StaticPointTargetModel(
        target_model_id="Effort KC",
        target_by_point_value={
            3: 35,
        },
    )

    with pytest.raises(
        ValueError,
        match="target_model_id",
    ):
        build_single_tile_candidate(
            component,
            3,
            target_model,
        )


def test_build_single_experience_candidate_from_component():
    component = TileComponent(
        component_id="Magic XP",
        component_type=TileComponentType.EXPERIENCE,
        display_name="Magic",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static XP",
        skill_id="Magic",
    )
    target_model = StaticPointTargetModel(
        target_model_id="Static XP",
        target_by_point_value={
            2: 500000,
        },
    )

    candidate = build_single_tile_candidate(
        component,
        2,
        target_model,
    )
    route = candidate.routes[0]

    assert candidate.title == "Gain 500,000 Magic XP"
    assert candidate.primary_category == TileCategory.SKILL
    assert route.route_type == TileCategory.SKILL
    assert route.display_text == "Gain 500,000 Magic XP"
    assert route.target == 500000
    assert route.metric_id == "skill_magic_xp"
    assert route.source_id == "magic"
    assert route.skill_id == "magic"
    assert "component:magic_xp" in candidate.all_hard_unique_tags
    assert "skill:magic" in candidate.all_hard_unique_tags


def test_build_single_candidate_can_suppress_generation_note():
    component = TileComponent(
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
    target_model = StaticPointTargetModel(
        target_model_id="Static KC",
        target_by_point_value={
            3: 35,
        },
    )

    candidate = build_single_tile_candidate(
        component,
        3,
        target_model,
        explanation=(
            "Template note.",
        ),
        include_generation_note=False,
    )

    assert candidate.explanation == (
        "Component note.",
        "Template note.",
    )
    assert all(
        not tag.startswith("target_model:")
        for tag in candidate.all_hard_unique_tags
    )



def test_build_single_wom_metric_candidate_from_component():
    component = TileComponent(
        component_id="Medium Clues",
        component_type=TileComponentType.WOM_METRIC,
        display_name="medium clue scrolls",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static Metric",
        metric_id="Medium Clues Completed",
        source_id="Medium Clues",
        groups=(
            "Clue Scrolls",
        ),
    )
    target_model = StaticPointTargetModel(
        target_model_id="Static Metric",
        target_by_point_value={
            2: 25,
        },
    )

    candidate = build_single_tile_candidate(
        component,
        2,
        target_model,
    )
    route = candidate.routes[0]

    assert candidate.title == "Complete 25 medium clue scrolls"
    assert candidate.primary_category == TileCategory.HYBRID
    assert route.route_type == TileCategory.HYBRID
    assert route.display_text == "Complete 25 medium clue scrolls"
    assert route.target == 25
    assert route.metric_id == "medium_clues_completed"
    assert route.source_id == "medium_clues"
    assert "component:medium_clues" in candidate.all_hard_unique_tags
    assert "metric:medium_clues_completed" in candidate.all_hard_unique_tags
    assert "source:medium_clues" in candidate.all_hard_unique_tags
    assert "activity_group:clue_scrolls" in candidate.all_hard_unique_tags

def test_build_single_candidate_still_rejects_unimplemented_component_type():
    component = TileComponent(
        component_id="Rocky Pet",
        component_type=TileComponentType.PET,
        display_name="Rocky",
        tracking_source=TrackingSource.DINK,
        target_model_id="Pet Drop",
        pet_id="Rocky",
    )
    target_model = StaticPointTargetModel(
        target_model_id="Pet Drop",
        target_by_point_value={
            5: 1,
        },
    )

    with pytest.raises(
        ValueError,
        match="currently supports KILLCOUNT, EXPERIENCE and WOM_METRIC",
    ):
        build_single_tile_candidate(
            component,
            5,
            target_model,
        )
