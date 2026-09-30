import pytest

from utils.osrs_tile_component_catalogue import (
    build_tile_component_catalogue_summary,
    get_curated_tile_component_catalogue_summary,
    get_curated_tile_components,
    get_static_drop_components,
    get_static_killcount_components,
    get_static_metric_components,
    get_static_pet_components,
    get_static_skill_xp_components,
    validate_unique_component_ids,
)
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)
from utils.board_generation import TrackingSource


def test_static_component_views_expose_expected_source_counts():
    assert len(
        get_static_pet_components()
    ) == 71
    assert len(
        get_static_metric_components()
    ) == 6
    assert len(
        get_static_killcount_components()
    ) == 10
    assert len(
        get_static_drop_components()
    ) == 10
    assert len(
        get_static_skill_xp_components()
    ) == 24


def test_curated_tile_components_are_unique_atomic_parts():
    components = get_curated_tile_components()
    component_ids = [
        component.component_id
        for component in components
    ]

    assert len(components) == 121
    assert len(component_ids) == len(
        set(
            component_ids
        )
    )
    assert "zulrah_killcount" in component_ids
    assert "zulrah_drop" in component_ids
    assert "magic_experience" in component_ids
    assert "vorki_pet" in component_ids
    assert "guardians_of_the_rift_completions_metric" in component_ids


def test_curated_component_catalogue_summary_counts_components():
    summary = get_curated_tile_component_catalogue_summary()

    assert summary.component_count == 121
    assert summary.counts_by_component_type == {
        "DROP": 10,
        "EXPERIENCE": 24,
        "KILLCOUNT": 10,
        "PET": 71,
        "WOM_METRIC": 6,
    }
    assert summary.counts_by_primary_category == {
        "DROP": 10,
        "HYBRID": 6,
        "KILLCOUNT": 10,
        "PET": 71,
        "SKILL": 24,
    }
    assert summary.counts_by_tracking_source == {
        "DINK": 81,
        "WOM": 40,
    }


def test_component_catalogue_summary_groups_related_components():
    summary = get_curated_tile_component_catalogue_summary()

    assert summary.component_ids_by_group["clue_scrolls"] == (
        "clue_scrolls_elite_completed_metric",
        "clue_scrolls_hard_completed_metric",
        "clue_scrolls_medium_plus_completed_metric",
    )


def test_validate_unique_component_ids_rejects_duplicates():
    component = TileComponent(
        component_id="Duplicate",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Duplicate",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static",
        boss_id="Duplicate",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate component ids",
    ):
        validate_unique_component_ids(
            (
                component,
                component,
            )
        )


def test_build_tile_component_catalogue_summary_accepts_custom_components():
    component = TileComponent(
        component_id="Callisto KC",
        component_type=TileComponentType.KILLCOUNT,
        display_name="Callisto",
        tracking_source=TrackingSource.WOM,
        target_model_id="Static KC",
        boss_id="Callisto",
        groups=(
            "Wilderness Bosses",
        ),
    )

    summary = build_tile_component_catalogue_summary(
        (
            component,
        )
    )

    assert summary.component_count == 1
    assert summary.counts_by_component_type == {
        "KILLCOUNT": 1,
    }
    assert summary.component_ids_by_group == {
        "wilderness_bosses": (
            "callisto_kc",
        ),
    }
