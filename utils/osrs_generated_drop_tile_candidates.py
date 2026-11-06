"""Build generated DROP tile candidates from drop-effort preview rows."""

from dataclasses import replace

from utils.board_generation import AccessProfile, ContributionMode, TileCategory, TrackingSource
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
    target = generated_drop_target_for_row(row)
    display_name = row.display_name

    if target == 1 and display_name.endswith(" Uniques"):
        display_name = f"{display_name[:-8]} Unique"

    return f"Obtain {target} {display_name}"


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


def build_generated_repeatable_drop_tile_candidate(
    row,
    *,
    target,
    point_value,
):
    # Explicit opt-in recipe; not included in the active candidate pool.
    if (
        row.tile_mode != DROP_TILE_EFFORT_MODE_GROUP_UNIQUES
        or not is_supported_generated_drop_effort_row(row)
    ):
        raise ValueError(
            "Repeatable quantity recipes require a supported drop-group row."
        )

    if type(target) is not int or target < 1:
        raise ValueError("Quantity target must be a positive integer.")

    if type(point_value) is not int or not 1 <= point_value <= 5:
        raise ValueError("Point value must be an integer from 1 to 5.")

    component = build_generated_drop_component(row)

    target_model = StaticPointTargetModel(
        target_model_id=component.target_model_id,
        target_by_point_value=((point_value, target),),
    )

    title = (
        f"Obtain {target} {row.source_name} unique drops "
        "(duplicates allowed)"
    )

    candidate = build_single_tile_candidate(
        component,
        point_value,
        target_model,
        title=title,
        display_text=title,
        explanation=(
            "Repeatable quantity recipe; effort calibration pending.",
        ),
        include_generation_note=False,
    )

    route = candidate.routes[0]

    return replace(
        candidate,
        routes=(
            replace(
                route,
                contribution_mode=ContributionMode.TEAM_SUM,
                expected_rolls=None,
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


def build_provisional_verified_nonunique_drop_candidate(
    *,
    drop_id,
    source_id,
    target,
    point_value,
    drop_rows,
    verification_records,
):
    """Build an opt-in, source-verified non-unique DROP candidate.

    This is a provisional recipe, not an active catalogue entry.

    Verification records declare acquisition-source coverage but their
    underlying OSRS evidence must be independently reviewed.

    Difficulty, access, tracking and recipe activation still require
    separate validation before this candidate can become active.
    """
    from utils.board_generation import (
        ContributionMode,
        Route,
        RouteMode,
        TileCandidate,
        TileCategory,
        TrackingSource,
        build_tag,
    )
    from utils.osrs_drop_source_coverage import (
        select_source_verified_nonunique_drops,
    )

    if not isinstance(drop_id, str) or not drop_id.strip():
        raise ValueError("A valid drop ID is required.")

    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("A valid acquisition source ID is required.")

    if type(target) is not int or target < 1:
        raise ValueError("Target must be a positive integer.")

    if type(point_value) is not int or not 1 <= point_value <= 5:
        raise ValueError("Point value must be an integer from 1 to 5.")

    if drop_id != drop_id.strip():
        raise ValueError("Drop ID must not contain surrounding whitespace.")

    if source_id != source_id.strip():
        raise ValueError("Source ID must not contain surrounding whitespace.")

    rows = tuple(drop_rows)

    eligible = select_source_verified_nonunique_drops(
        rows,
        verification_records,
    )

    verified_source_ids = eligible.get(drop_id)

    if not verified_source_ids:
        raise ValueError(
            f"No complete, verified non-unique source coverage "
            f"for {drop_id}."
        )

    if source_id not in verified_source_ids:
        raise ValueError(
            f"Source {source_id} is not verified for {drop_id}."
        )

    matching_rows = tuple(
        row
        for row in rows
        if row.get("drop_id") == drop_id
    )

    if not matching_rows:
        raise ValueError(
            f"No recorded drop metadata found for {drop_id}."
        )

    drop_names = {
        row.get("drop_name")
        for row in matching_rows
    }

    if (
        len(drop_names) != 1
        or not all(
            isinstance(name, str) and name.strip()
            for name in drop_names
        )
    ):
        raise ValueError(
            f"Missing or inconsistent drop names for {drop_id}."
        )

    drop_name = next(iter(drop_names)).strip()

    source_tags = frozenset(
        build_tag("source", verified_source_id)
        for verified_source_id in verified_source_ids
    )

    if None in source_tags:
        raise ValueError("Invalid verified acquisition-source tag.")

    title = f"Obtain {target} {drop_name}"

    route = Route(
        route_type=TileCategory.DROP,
        display_text=title,
        target=target,
        tracking_source=TrackingSource.DINK,
        contribution_mode=ContributionMode.TEAM_SUM,
        # This is an item objective, not a boss-specific objective.
        # All acquisition sources are instead reserved below.
        source_id=None,
        drop_id=drop_id,
        hard_unique_tags=source_tags,
        expected_rolls=None,
    )

    return TileCandidate(
        title=title,
        point_value=point_value,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=(route,),
    )
