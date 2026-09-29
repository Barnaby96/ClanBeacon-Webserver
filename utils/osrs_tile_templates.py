from utils.board_generation import (
    AccessProfile,
    ContributionMode,
    PetRole,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
    canonical_id,
)
from utils.osrs_content_access import build_access_profile_for_content


def format_title_part(value):
    return str(value).replace("_", " ").title()


def format_target(value):
    if isinstance(value, int):
        return f"{value:,}"

    return str(value)


def access_profile_for_content(content_id):
    if content_id is None:
        return AccessProfile()

    return build_access_profile_for_content(
        content_id
    )


def make_killcount_candidate(
    title,
    point_value,
    boss_id,
    target,
    content_id=None,
    display_text=None,
    tracking_source=TrackingSource.WOM,
    contribution_mode=ContributionMode.TEAM_SUM,
    rng_level=0,
    explanation=(),
):
    boss_id = canonical_id(
        boss_id
    )
    source_id = canonical_id(
        content_id or boss_id
    )

    return TileCandidate(
        title=title,
        point_value=point_value,
        primary_category=TileCategory.KILLCOUNT,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.KILLCOUNT,
                display_text=(
                    display_text
                    or f"Complete {format_target(target)} "
                    f"{format_title_part(boss_id)} KC"
                ),
                target=target,
                tracking_source=tracking_source,
                contribution_mode=contribution_mode,
                metric_id=f"boss_{boss_id}_kc",
                source_id=source_id,
                boss_id=boss_id,
            )
        ],
        rng_level=rng_level,
        access_profile=access_profile_for_content(
            content_id
        ),
        explanation=tuple(
            explanation
        ),
    )


def make_drop_candidate(
    title,
    point_value,
    source_id,
    target=1,
    drop_id=None,
    drop_group_id=None,
    boss_id=None,
    content_id=None,
    display_text=None,
    tracking_source=TrackingSource.DINK,
    contribution_mode=ContributionMode.TEAM_SUM,
    rng_level=2,
    explanation=(),
):
    if drop_id is None and drop_group_id is None:
        raise ValueError(
            "Drop candidates require either drop_id or drop_group_id."
        )

    source_id = canonical_id(
        source_id
    )
    boss_id = canonical_id(
        boss_id
    )
    drop_id = canonical_id(
        drop_id
    )
    drop_group_id = canonical_id(
        drop_group_id
    )

    if drop_id is not None:
        metric_id = f"drop_{drop_id}"
        drop_label = format_title_part(
            drop_id
        )
    else:
        metric_id = f"drop_group_{drop_group_id}"
        drop_label = format_title_part(
            drop_group_id
        )

    return TileCandidate(
        title=title,
        point_value=point_value,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.DROP,
                display_text=(
                    display_text
                    or f"Obtain {drop_label}"
                ),
                target=target,
                tracking_source=tracking_source,
                contribution_mode=contribution_mode,
                metric_id=metric_id,
                source_id=source_id,
                boss_id=boss_id,
                drop_id=drop_id,
                drop_group_id=drop_group_id,
            )
        ],
        rng_level=rng_level,
        access_profile=access_profile_for_content(
            content_id
        ),
        explanation=tuple(
            explanation
        ),
    )


def make_pet_candidate(
    title,
    point_value,
    pet_id=None,
    pet_group_id=None,
    source_id=None,
    target=1,
    display_text=None,
    tracking_source=TrackingSource.DINK,
    contribution_mode=ContributionMode.ANY_PLAYER,
    rng_level=4,
    additional_hard_unique_tags=(),
    explanation=(),
):
    if pet_id is None and pet_group_id is None:
        raise ValueError(
            "Pet candidates require either pet_id or pet_group_id."
        )

    pet_id = canonical_id(
        pet_id
    )
    pet_group_id = canonical_id(
        pet_group_id
    )
    source_id = canonical_id(
        source_id or pet_group_id or pet_id
    )

    if pet_id is not None:
        metric_id = f"pet_{pet_id}"
        pet_label = format_title_part(
            pet_id
        )
    else:
        metric_id = f"pet_group_{pet_group_id}"
        pet_label = format_title_part(
            pet_group_id
        )

    return TileCandidate(
        title=title,
        point_value=point_value,
        primary_category=TileCategory.PET,
        pet_role=PetRole.PRIMARY,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.PET,
                display_text=(
                    display_text
                    or f"Obtain {pet_label}"
                ),
                target=target,
                tracking_source=tracking_source,
                contribution_mode=contribution_mode,
                metric_id=metric_id,
                source_id=source_id,
                pet_id=pet_id,
                pet_group_id=pet_group_id,
                hard_unique_tags=frozenset(
                    additional_hard_unique_tags
                ),
            )
        ],
        rng_level=rng_level,
        explanation=tuple(
            explanation
        ),
    )


def make_skill_xp_candidate(
    title,
    point_value,
    skill_id,
    xp_target,
    display_text=None,
    tracking_source=TrackingSource.WOM,
    contribution_mode=ContributionMode.TEAM_SUM,
    rng_level=0,
    explanation=(),
):
    skill_id = canonical_id(
        skill_id
    )

    return TileCandidate(
        title=title,
        point_value=point_value,
        primary_category=TileCategory.SKILL,
        route_mode=RouteMode.SINGLE,
        routes=[
            Route(
                route_type=TileCategory.SKILL,
                display_text=(
                    display_text
                    or f"Gain {format_target(xp_target)} "
                    f"{format_title_part(skill_id)} XP"
                ),
                target=xp_target,
                tracking_source=tracking_source,
                contribution_mode=contribution_mode,
                metric_id=f"skill_{skill_id}_xp",
                source_id=skill_id,
                skill_id=skill_id,
            )
        ],
        rng_level=rng_level,
        explanation=tuple(
            explanation
        ),
    )


def make_skill_xp_or_pet_candidate(
    title,
    point_value,
    skill_id,
    xp_target,
    pet_id,
    xp_display_text=None,
    pet_display_text=None,
    rng_level=4,
    explanation=(),
):
    skill_id = canonical_id(
        skill_id
    )
    pet_id = canonical_id(
        pet_id
    )

    return TileCandidate(
        title=title,
        point_value=point_value,
        primary_category=TileCategory.SKILL,
        secondary_categories=frozenset(
            {
                TileCategory.PET
            }
        ),
        pet_role=PetRole.SECONDARY,
        route_mode=RouteMode.OR,
        routes=[
            Route(
                route_type=TileCategory.SKILL,
                display_text=(
                    xp_display_text
                    or f"Gain {format_target(xp_target)} "
                    f"{format_title_part(skill_id)} XP"
                ),
                target=xp_target,
                tracking_source=TrackingSource.WOM,
                contribution_mode=ContributionMode.TEAM_SUM,
                metric_id=f"skill_{skill_id}_xp",
                source_id=skill_id,
                skill_id=skill_id,
            ),
            Route(
                route_type=TileCategory.PET,
                display_text=(
                    pet_display_text
                    or f"Obtain {format_title_part(pet_id)}"
                ),
                target=1,
                tracking_source=TrackingSource.DINK,
                contribution_mode=ContributionMode.ANY_PLAYER,
                metric_id=f"pet_{pet_id}",
                source_id=skill_id,
                skill_id=skill_id,
                pet_id=pet_id,
            ),
        ],
        rng_level=rng_level,
        has_fallback=True,
        explanation=tuple(
            explanation
        ),
    )
