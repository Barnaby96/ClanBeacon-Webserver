"""Curated OSRS Bingo component catalogue views."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from utils.osrs_pets import get_osrs_pet_options
from utils.osrs_tile_catalogue import build_pet_component_from_option
from utils.osrs_tile_template_expansion import (
    STATIC_DROP_TEMPLATES,
    STATIC_KILLCOUNT_TEMPLATES,
    STATIC_METRIC_TEMPLATES,
    STATIC_SKILL_XP_TEMPLATES,
    build_drop_component_from_template,
    build_killcount_component_from_template,
    build_metric_component_from_template,
    build_skill_xp_component_from_template,
)


@dataclass(frozen=True)
class TileComponentCatalogueSummary:
    component_count: int
    counts_by_component_type: dict
    counts_by_primary_category: dict
    counts_by_tracking_source: dict
    component_ids_by_group: dict


def get_static_killcount_components():
    return tuple(
        build_killcount_component_from_template(
            template
        )
        for template in STATIC_KILLCOUNT_TEMPLATES
    )


def get_static_drop_components():
    return tuple(
        build_drop_component_from_template(
            template
        )
        for template in STATIC_DROP_TEMPLATES
    )


def get_static_skill_xp_components():
    return tuple(
        build_skill_xp_component_from_template(
            template
        )
        for template in STATIC_SKILL_XP_TEMPLATES
    )


def get_static_metric_components():
    return tuple(
        build_metric_component_from_template(
            template
        )
        for template in STATIC_METRIC_TEMPLATES
    )


def get_static_pet_components():
    return tuple(
        build_pet_component_from_option(
            option
        )
        for option in get_osrs_pet_options()
    )


def get_curated_tile_components():
    return (
        *get_static_pet_components(),
        *get_static_metric_components(),
        *get_static_killcount_components(),
        *get_static_drop_components(),
        *get_static_skill_xp_components(),
    )


def validate_unique_component_ids(components):
    component_ids = [
        component.component_id
        for component in components
    ]
    duplicate_component_ids = sorted(
        component_id
        for component_id, count in Counter(
            component_ids
        ).items()
        if count > 1
    )

    if duplicate_component_ids:
        raise ValueError(
            "Duplicate component ids: "
            + ", ".join(
                duplicate_component_ids
            )
        )

    return tuple(
        components
    )


def build_tile_component_catalogue_summary(components):
    components = validate_unique_component_ids(
        tuple(
            components
        )
    )

    component_ids_by_group = defaultdict(
        list
    )

    for component in components:
        for group in component.groups:
            component_ids_by_group[group].append(
                component.component_id
            )

    return TileComponentCatalogueSummary(
        component_count=len(
            components
        ),
        counts_by_component_type=dict(
            sorted(
                Counter(
                    component.component_type.value
                    for component in components
                ).items()
            )
        ),
        counts_by_primary_category=dict(
            sorted(
                Counter(
                    component.primary_category.value
                    for component in components
                ).items()
            )
        ),
        counts_by_tracking_source=dict(
            sorted(
                Counter(
                    component.tracking_source.value
                    for component in components
                ).items()
            )
        ),
        component_ids_by_group={
            group: tuple(
                sorted(
                    component_ids
                )
            )
            for group, component_ids in sorted(
                component_ids_by_group.items()
            )
        },
    )


def get_curated_tile_component_catalogue_summary():
    return build_tile_component_catalogue_summary(
        get_curated_tile_components()
    )
