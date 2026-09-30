"""Generation recipes for turning components into tile candidates."""

from dataclasses import dataclass
from enum import Enum

from utils.board_generation import (
    ContributionMode,
    PetRole,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    canonical_id,
)
from utils.osrs_tile_components import (
    TileComponent,
    TileComponentType,
)


class GenerationRecipeId(str, Enum):
    SINGLE = "SINGLE"
    N_OF = "N_OF"


@dataclass(frozen=True)
class StaticPointTargetModel:
    target_model_id: str
    target_by_point_value: tuple

    def __post_init__(self):
        target_model_id = canonical_id(
            self.target_model_id
        )

        if target_model_id is None or target_model_id == "":
            raise ValueError("Target models require a target_model_id.")

        targets = {}

        if hasattr(
            self.target_by_point_value,
            "items",
        ):
            items = self.target_by_point_value.items()
        else:
            items = self.target_by_point_value

        for point_value, target in items:
            if point_value < 1 or point_value > 5:
                raise ValueError(
                    "Target model point values must be between 1 and 5."
                )

            if point_value in targets:
                raise ValueError(
                    f"Duplicate target for {point_value}-point tiles."
                )

            if target <= 0:
                raise ValueError(
                    "Target model targets must be positive."
                )

            targets[int(point_value)] = target

        if not targets:
            raise ValueError("Target models require at least one target.")

        object.__setattr__(
            self,
            "target_model_id",
            target_model_id,
        )
        object.__setattr__(
            self,
            "target_by_point_value",
            tuple(
                sorted(
                    targets.items()
                )
            ),
        )

    def target_for_point_value(self, point_value):
        targets = dict(
            self.target_by_point_value
        )

        if point_value not in targets:
            raise ValueError(
                f"No target for {point_value}-point tiles."
            )

        return targets[point_value]


@dataclass(frozen=True)
class GenerationRecipe:
    recipe_id: GenerationRecipeId
    route_mode: RouteMode
    required_route_count: int | None = None

    def __post_init__(self):
        object.__setattr__(
            self,
            "recipe_id",
            GenerationRecipeId(
                self.recipe_id
            ),
        )
        object.__setattr__(
            self,
            "route_mode",
            RouteMode(
                self.route_mode
            ),
        )


SINGLE_RECIPE = GenerationRecipe(
    recipe_id=GenerationRecipeId.SINGLE,
    route_mode=RouteMode.SINGLE,
)


N_OF_RECIPE = GenerationRecipe(
    recipe_id=GenerationRecipeId.N_OF,
    route_mode=RouteMode.N_OF,
)


def format_target(value):
    if isinstance(
        value,
        int,
    ):
        return f"{value:,}"

    return str(
        value
    )


def build_single_killcount_route(component, target, display_text=None):
    if not component.boss_id:
        raise ValueError(
            "Killcount components require a boss_id."
        )

    source_id = component.source_id or component.boss_id
    metric_id = component.metric_id or f"boss_{component.boss_id}_kc"

    return Route(
        route_type=TileCategory.KILLCOUNT,
        display_text=(
            display_text
            or f"Complete {format_target(target)} "
            f"{component.display_name} KC"
        ),
        target=target,
        tracking_source=component.tracking_source,
        contribution_mode=ContributionMode.TEAM_SUM,
        metric_id=metric_id,
        source_id=source_id,
        boss_id=component.boss_id,
        hard_unique_tags=component.hard_unique_tags,
    )


def build_single_experience_route(component, target, display_text=None):
    if not component.skill_id:
        raise ValueError(
            "Experience components require a skill_id."
        )

    metric_id = component.metric_id or f"skill_{component.skill_id}_xp"
    source_id = component.source_id or component.skill_id

    return Route(
        route_type=TileCategory.SKILL,
        display_text=(
            display_text
            or f"Gain {format_target(target)} "
            f"{component.display_name} XP"
        ),
        target=target,
        tracking_source=component.tracking_source,
        contribution_mode=ContributionMode.TEAM_SUM,
        metric_id=metric_id,
        source_id=source_id,
        skill_id=component.skill_id,
        hard_unique_tags=component.hard_unique_tags,
    )


def build_single_wom_metric_route(component, target, display_text=None):
    if not component.metric_id:
        raise ValueError(
            "WOM metric components require a metric_id."
        )

    source_id = component.source_id or component.metric_id

    return Route(
        route_type=TileCategory.HYBRID,
        display_text=(
            display_text
            or f"Complete {format_target(target)} "
            f"{component.display_name}"
        ),
        target=target,
        tracking_source=component.tracking_source,
        contribution_mode=ContributionMode.TEAM_SUM,
        metric_id=component.metric_id,
        source_id=source_id,
        hard_unique_tags=component.hard_unique_tags,
    )


def build_single_drop_route(component, target, display_text=None):
    if not component.drop_id and not component.drop_group_id:
        raise ValueError(
            "Drop components require a drop_id or drop_group_id."
        )

    source_id = (
        component.source_id
        or component.boss_id
        or component.drop_group_id
        or component.drop_id
    )

    return Route(
        route_type=TileCategory.DROP,
        display_text=(
            display_text
            or f"Obtain {format_target(target)} "
            f"{component.display_name}"
        ),
        target=target,
        tracking_source=component.tracking_source,
        contribution_mode=ContributionMode.TEAM_SUM,
        source_id=source_id,
        boss_id=component.boss_id,
        drop_id=component.drop_id,
        drop_group_id=component.drop_group_id,
        hard_unique_tags=component.hard_unique_tags,
    )


def build_single_pet_route(component, target, display_text=None):
    if not component.pet_id:
        raise ValueError(
            "Pet components require a pet_id."
        )

    source_id = component.source_id or component.pet_id

    return Route(
        route_type=TileCategory.PET,
        display_text=(
            display_text
            or f"Obtain {component.display_name}"
        ),
        target=target,
        tracking_source=component.tracking_source,
        contribution_mode=ContributionMode.ANY_PLAYER,
        metric_id=component.metric_id,
        source_id=source_id,
        pet_id=component.pet_id,
        hard_unique_tags=component.hard_unique_tags,
    )


def build_single_route(component, target, display_text=None):
    if component.component_type == TileComponentType.KILLCOUNT:
        return build_single_killcount_route(
            component,
            target,
            display_text=display_text,
        )

    if component.component_type == TileComponentType.EXPERIENCE:
        return build_single_experience_route(
            component,
            target,
            display_text=display_text,
        )

    if component.component_type == TileComponentType.WOM_METRIC:
        return build_single_wom_metric_route(
            component,
            target,
            display_text=display_text,
        )

    if component.component_type == TileComponentType.DROP:
        return build_single_drop_route(
            component,
            target,
            display_text=display_text,
        )

    if component.component_type == TileComponentType.PET:
        return build_single_pet_route(
            component,
            target,
            display_text=display_text,
        )

    raise ValueError(
        "SINGLE recipe currently supports KILLCOUNT, EXPERIENCE, "
        "WOM_METRIC, DROP and PET components only."
    )


def build_single_tile_candidate(
    component: TileComponent,
    point_value,
    target_model: StaticPointTargetModel,
    title=None,
    display_text=None,
    explanation=(),
    include_generation_note=True,
):
    if not component.supports_recipe(
        GenerationRecipeId.SINGLE.value
    ):
        raise ValueError(
            f"Component {component.component_id} does not support "
            "the SINGLE recipe."
        )

    if component.target_model_id != target_model.target_model_id:
        raise ValueError(
            "Component target_model_id does not match target model."
        )

    target = target_model.target_for_point_value(
        point_value
    )
    route = build_single_route(
        component,
        target,
        display_text=display_text,
    )

    explanation_entries = (
        *component.notes,
        *tuple(
            explanation
        ),
    )

    if include_generation_note:
        explanation_entries = (
            *explanation_entries,
            (
                f"Generated {point_value}-point SINGLE tile "
                f"from component {component.component_id}."
            ),
        )

    return TileCandidate(
        title=title or route.display_text,
        point_value=point_value,
        primary_category=component.primary_category,
        route_mode=SINGLE_RECIPE.route_mode,
        routes=(
            route,
        ),
        pet_role=(
            PetRole.PRIMARY
            if component.component_type == TileComponentType.PET
            else PetRole.NONE
        ),
        rng_level=component.rng_level,
        access_profile=component.access_profile,
        explanation=explanation_entries,
    )


def build_n_of_tile_candidate(
    components,
    point_value,
    target_model_by_component_id,
    required_route_count,
    title,
    explanation=(),
):
    components = tuple(
        components
    )

    if not components:
        raise ValueError(
            "N_OF recipes require at least one component."
        )

    if required_route_count < 1:
        raise ValueError(
            "N_OF required_route_count must be positive."
        )

    if required_route_count > len(
        components
    ):
        raise ValueError(
            "N_OF required_route_count cannot exceed component count."
        )

    routes = []

    for component in components:
        if not component.supports_recipe(
            GenerationRecipeId.N_OF.value
        ):
            raise ValueError(
                f"Component {component.component_id} does not support "
                "the N_OF recipe."
            )

        if component.component_id not in target_model_by_component_id:
            raise ValueError(
                f"Missing target model for component {component.component_id}."
            )

        target_model = target_model_by_component_id[
            component.component_id
        ]

        if component.target_model_id != target_model.target_model_id:
            raise ValueError(
                f"Target model mismatch for component {component.component_id}."
            )

        target = target_model.target_for_point_value(
            point_value
        )

        routes.append(
            build_single_route(
                component,
                target,
            )
        )

    primary_category = components[0].primary_category
    secondary_categories = frozenset(
        component.primary_category
        for component in components[1:]
        if component.primary_category != primary_category
    )

    return TileCandidate(
        title=title,
        point_value=point_value,
        primary_category=primary_category,
        secondary_categories=secondary_categories,
        route_mode=N_OF_RECIPE.route_mode,
        routes=tuple(
            routes
        ),
        required_route_count=required_route_count,
        rng_level=max(
            component.rng_level
            for component in components
        ),
        explanation=(
            *tuple(
                explanation
            ),
            (
                f"Generated {point_value}-point N_OF tile requiring "
                f"{required_route_count} of {len(components)} routes."
            ),
        ),
    )
