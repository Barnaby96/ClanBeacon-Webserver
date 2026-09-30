import pytest

from utils.board_generation import (
    AccessFlag,
    AccessProfile,
    TileCategory,
    TrackingSource,
)
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)


def test_tile_component_normalises_identity_and_tags():
    component = TileComponent(
        component_id="Callisto KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Callisto killcount",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        source_id="Callisto",
        boss_id="Callisto",
        groups=(
            "Wilderness Bosses",
        ),
    )

    assert component.component_id == "callisto_kc"
    assert component.component_type == TileComponentType.KILLCOUNT
    assert component.primary_category == TileCategory.KILLCOUNT
    assert component.tracking_source == TrackingSource.WOM
    assert component.target_model_id == "static_kc"
    assert component.groups == (
        "wilderness_bosses",
    )
    assert component.hard_unique_tags == frozenset(
        {
            "component:callisto_kc",
            "source:callisto",
            "boss:callisto",
            "activity_group:wilderness_bosses",
        }
    )


def test_experience_component_defaults_to_skill_category():
    component = TileComponent(
        component_id="Magic XP",
        component_type=TileComponentType.EXPERIENCE,
        display_name="Magic experience",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static XP",
        skill_id="Magic",
        groups=(
            "Combat Skills",
        ),
    )

    assert component.primary_category == TileCategory.SKILL
    assert component.hard_unique_tags == frozenset(
        {
            "component:magic_xp",
            "skill:magic",
            "activity_group:combat_skills",
        }
    )


def test_pet_component_defaults_to_pet_category_and_dink_source():
    component = TileComponent(
        component_id="Rocky Pet",
        component_type=TileComponentType.PET,
        display_name="Rocky",
        tracking_source=TrackingSource.DINK,
        target_model_id="Pet Drop",
        pet_id="Rocky",
        groups=(
            "Skilling Pets",
        ),
    )

    assert component.primary_category == TileCategory.PET
    assert component.hard_unique_tags == frozenset(
        {
            "component:rocky_pet",
            "pet:rocky",
            "activity_group:skilling_pets",
        }
    )


def test_component_preserves_access_profile():
    access_profile = AccessProfile(
        effective_skill_requirements={
            "magic": 75,
        },
        access_flags=frozenset(
            {
                AccessFlag.QUEST_LOCKED,
            }
        ),
    )

    component = TileComponent(
        component_id="Vorkath KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Vorkath killcount",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        source_id="Vorkath",
        boss_id="Vorkath",
        access_profile=access_profile,
    )

    assert component.access_profile is access_profile


def test_component_recipe_support_is_normalised():
    component = TileComponent(
        component_id="Medium Clues",
        component_type=TileComponentType.WOM_METRIC,
        display_name="Medium clue completions",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static Metric",
        metric_id="Medium Clues",
        source_id="Medium Clues",
        groups=(
            "Clue Scrolls",
        ),
        compatible_recipe_ids=(
            "single",
            "n_of",
        ),
    )

    assert component.primary_category == TileCategory.HYBRID
    assert component.supports_recipe("SINGLE")
    assert component.supports_recipe("N OF")
    assert not component.supports_recipe("SUM")


def test_component_rejects_invalid_minimum_fields():
    with pytest.raises(
        ValueError,
        match="component_id",
    ):
        TileComponent(
            component_id="",
            component_type=TileComponentType.KILLCOUNT,
            display_name="Callisto killcount",
            tracking_source=TrackingSource.WOM,
            target_model_id="Static KC",
        )


def test_component_rejects_duplicate_groups():
    with pytest.raises(
        ValueError,
        match="groups must be unique",
    ):
        TileComponent(
            component_id="Hard Clues",
            component_type=TileComponentType.WOM_METRIC,
            display_name="Hard clue completions",
            tracking_source=TrackingSource.WOM,
            target_model_id="Static Metric",
            groups=(
                "Clue Scrolls",
                "clue_scrolls",
            ),
        )
