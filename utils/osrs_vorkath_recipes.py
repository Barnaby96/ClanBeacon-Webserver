"""Provisional Vorkath procedural recipes.

These builders are not registered in the active catalogue.
Difficulty and access verification are required before activation.
"""

from dataclasses import replace

from utils.board_generation import (
    PetRole,
    RouteMode,
    TileCategory,
)
from utils.osrs_tile_catalogue import (
    get_curated_tile_generation_candidates,
)


def build_vorkath_pet_or_kc_candidate(*, kc_target, point_value):
    """Build an optional Vorki alternative to existing Vorkath KC."""
    if type(kc_target) is not int or kc_target <= 0:
        raise ValueError("KC target must be a positive integer.")

    if type(point_value) is not int or not 1 <= point_value <= 5:
        raise ValueError("Point value must be between 1 and 5.")

    catalogue = get_curated_tile_generation_candidates()

    matching_kc = [
        candidate
        for candidate in catalogue
        if candidate.primary_category == TileCategory.KILLCOUNT
        and candidate.point_value == point_value
        and candidate.route_mode == RouteMode.SINGLE
        and len(candidate.routes) == 1
        and candidate.routes[0].boss_id == "vorkath"
        and candidate.routes[0].target == kc_target
    ]

    matching_pet = [
        candidate
        for candidate in catalogue
        if candidate.primary_category == TileCategory.PET
        and candidate.route_mode == RouteMode.SINGLE
        and len(candidate.routes) == 1
        and candidate.routes[0].pet_id == "vorki"
        and candidate.routes[0].source_id == "vorkath"
    ]

    if len(matching_kc) != 1 or len(matching_pet) != 1:
        raise ValueError(
            "Expected exactly one existing Vorkath KC candidate "
            "and one Vorki candidate."
        )

    kc_candidate = matching_kc[0]
    pet_candidate = matching_pet[0]

    if kc_candidate.access_profile != pet_candidate.access_profile:
        raise ValueError(
            "Vorkath KC and Vorki access profiles differ; "
            "access reconciliation is required."
        )

    routes = (
        kc_candidate.routes[0],
        pet_candidate.routes[0],
    )

    return replace(
        kc_candidate,
        title=(
            f"Complete {kc_target} Vorkath KC OR obtain Vorki"
        ),
        route_mode=RouteMode.OR,
        routes=routes,
        primary_category=TileCategory.KILLCOUNT,
        secondary_categories=frozenset({
            TileCategory.PET,
        }),
        pet_role=PetRole.SECONDARY,
        has_fallback=False,
        rng_level=max(
            kc_candidate.rng_level,
            pet_candidate.rng_level,
        ),
        tracking_sources=frozenset(
            route.tracking_source
            for route in routes
        ),
        hard_unique_tags=(
            kc_candidate.hard_unique_tags
            | pet_candidate.hard_unique_tags
        ),
        explanation=(
            "Provisional PET OR KC recipe.",
            "Difficulty calibration and activation pending.",
        ),
    )


def build_vorkath_pet_or_unique_candidate(
    *,
    distinct_drop_target,
    point_value,
):
    """Build a provisional Vorkath unique-group OR Vorki objective."""
    from utils.board_generation import ContributionMode

    if type(distinct_drop_target) is not int or distinct_drop_target < 1:
        raise ValueError(
            "Distinct-drop target must be a positive integer."
        )

    if type(point_value) is not int or not 1 <= point_value <= 5:
        raise ValueError(
            "Point value must be an integer from 1 to 5."
        )

    catalogue = get_curated_tile_generation_candidates()

    matching_drops = [
        candidate
        for candidate in catalogue
        if candidate.primary_category == TileCategory.DROP
        and candidate.point_value == point_value
        and candidate.route_mode == RouteMode.SINGLE
        and len(candidate.routes) == 1
        and candidate.routes[0].source_id == "vorkath"
        and candidate.routes[0].drop_group_id == "vorkath_uniques"
        and candidate.routes[0].drop_id is None
        and candidate.routes[0].target == distinct_drop_target
        and (
            candidate.routes[0].contribution_mode
            == ContributionMode.N_OF_UNIQUES
        )
    ]

    matching_pets = [
        candidate
        for candidate in catalogue
        if candidate.primary_category == TileCategory.PET
        and candidate.route_mode == RouteMode.SINGLE
        and len(candidate.routes) == 1
        and candidate.routes[0].pet_id == "vorki"
        and candidate.routes[0].source_id == "vorkath"
    ]

    if len(matching_drops) != 1 or len(matching_pets) != 1:
        raise ValueError(
            "Expected exactly one matching Vorkath distinct-drop "
            "candidate and one Vorki candidate."
        )

    drop_candidate = matching_drops[0]
    pet_candidate = matching_pets[0]

    if drop_candidate.access_profile != pet_candidate.access_profile:
        raise ValueError(
            "Vorkath unique and Vorki access profiles differ; "
            "access reconciliation is required."
        )

    routes = (
        drop_candidate.routes[0],
        pet_candidate.routes[0],
    )

    drop_word = (
        "Unique" if distinct_drop_target == 1 else "Uniques"
    )

    return replace(
        drop_candidate,
        title=(
            f"Obtain {distinct_drop_target} Vorkath "
            f"{drop_word} OR obtain Vorki"
        ),
        route_mode=RouteMode.OR,
        routes=routes,
        primary_category=TileCategory.DROP,
        secondary_categories=frozenset({
            TileCategory.PET,
        }),
        pet_role=PetRole.SECONDARY,
        has_fallback=False,
        rng_level=max(
            drop_candidate.rng_level,
            pet_candidate.rng_level,
        ),
        tracking_sources=frozenset(
            route.tracking_source
            for route in routes
        ),
        hard_unique_tags=(
            drop_candidate.hard_unique_tags
            | pet_candidate.hard_unique_tags
        ),
        explanation=(
            "Provisional PET OR distinct-drop recipe.",
            "Difficulty calibration and activation pending.",
        ),
    )
