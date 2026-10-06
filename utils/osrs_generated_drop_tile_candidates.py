"""Build generated DROP tile candidates from drop-effort preview rows."""

from dataclasses import replace

from utils.board_generation import AccessProfile, TileCategory, TrackingSource
from utils.osrs_drop_tile_effort import (
    DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
    DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
)
from utils.osrs_drop_tile_effort_preview import (
    build_drop_tile_effort_preview_rows,
)
from utils.osrs_generation_recipes import (
    StaticPointTargetModel,
    build_single_tile_candidate,
)
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)
from utils.osrs_content_access import ContentAccessError
from utils.osrs_content_access import ContentAccessError
from utils.osrs_tile_templates import access_profile_for_content


SUPPORTED_GENERATED_DROP_TILE_MODES = frozenset(
    (
        DROP_TILE_EFFORT_MODE_GROUP_UNIQUES,
        DROP_TILE_EFFORT_MODE_SPECIFIC_DROP,
    )
)


def is_specific_drop_effort_row(row):
    return row.tile_mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP


def generated_drop_target_for_row(row):
    return 1 if is_specific_drop_effort_row(row) else row.target


def is_supported_generated_drop_effort_row(row):
    return (
        row.tile_mode in SUPPORTED_GENERATED_DROP_TILE_MODES
        and row.parseable
        and row.suggested_point_value is not None
        and generated_drop_target_for_row(row) is not None
        and row.drop_group_id
        and row.source_id
        and (
            not is_specific_drop_effort_row(row)
            or bool(row.drop_id)
        )
    )


def format_generated_group_drop_title(row):
    return f"Obtain {row.target} {row.display_name}"


def format_generated_specific_drop_title(row):
    return f"Obtain {row.drop_name}"


def access_profile_for_generated_drop_source(source_id):
    try:
        return access_profile_for_content(source_id)
    except ContentAccessError:
        return AccessProfile()


def access_profile_for_generated_drop_source(source_id):
    try:
        return access_profile_for_content(source_id)
    except ContentAccessError:
        return AccessProfile()


def build_generated_drop_component(row):
    is_specific_drop = is_specific_drop_effort_row(row)

    return TileComponent(
        component_id=(
            f"{row.source_id}_{row.drop_id}_generated_drop"
            if is_specific_drop
            else f"{row.source_id}_{row.drop_group_id}_generated_drop"
        ),
        component_type=TileComponentType.DROP,
        display_name=(
            row.drop_name
            if is_specific_drop
            else row.display_name
        ),
        tracking_source=TrackingSource.DINK,
        target_model_id=(
            f"{row.source_id}_{row.drop_id}_generated_drop_target"
            if is_specific_drop
            else f"{row.source_id}_{row.drop_group_id}_generated_drop_target"
        ),
        primary_category=TileCategory.DROP,
        source_id=row.source_id,
        drop_id=(
            row.drop_id
            if is_specific_drop
            else None
        ),
        drop_group_id=row.drop_group_id,
        access_profile=access_profile_for_generated_drop_source(
            row.source_id
        ),
        rng_level=min(row.suggested_point_value, 4),
        notes=(
            row.reason,
            row.source_effort_reason,
        ),
    )


def build_generated_drop_target_model(row):
    return StaticPointTargetModel(
        target_model_id=(
            f"{row.source_id}_{row.drop_id}_generated_drop_target"
            if row.tile_mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
            else f"{row.source_id}_{row.drop_group_id}_generated_drop_target"
        ),
        target_by_point_value=(
            (
                row.suggested_point_value,
                generated_drop_target_for_row(row),
            ),
        ),
    )


def build_generated_drop_tile_candidate(row):
    component = build_generated_drop_component(
        row
    )
    target_model = build_generated_drop_target_model(
        row
    )

    title = (
        format_generated_specific_drop_title(row)
        if row.tile_mode == DROP_TILE_EFFORT_MODE_SPECIFIC_DROP
        else format_generated_group_drop_title(row)
    )

    candidate = build_single_tile_candidate(
        component,
        row.suggested_point_value,
        target_model,
        title=title,
        display_text=title,
        explanation=(
            f"Generated from drop effort preview row for {row.source_name}.",
        ),
        include_generation_note=False,
    )

    route = candidate.routes[0]

    return replace(
        candidate,
        routes=(
            replace(
                route,
                expected_rolls=row.expected_rolls,
            ),
        ),
    )


def build_generated_drop_tile_candidates(rows=None):
    rows = (
        build_drop_tile_effort_preview_rows()
        if rows is None
        else rows
    )

    return tuple(
        build_generated_drop_tile_candidate(row)
        for row in rows
        if is_supported_generated_drop_effort_row(row)
    )






