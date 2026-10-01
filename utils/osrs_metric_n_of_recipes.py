"""N_OF recipe builders for WOM metric component groups."""

from utils.osrs_generation_recipes import (
    GenerationRecipeId,
    build_n_of_tile_candidate,
)
from utils.osrs_tile_component_catalogue import get_static_metric_components
from utils.osrs_tile_component_selection import (
    ComponentSelectionCriteria,
    require_component_count,
    select_components,
)
from utils.osrs_tile_components import TileComponentType
from utils.osrs_tile_template_expansion import (
    STATIC_METRIC_TEMPLATES,
    build_metric_component_from_template,
    build_metric_target_model_from_template,
)


def get_static_metric_target_models_by_component_id():
    target_models = {}

    for template in STATIC_METRIC_TEMPLATES:
        component = build_metric_component_from_template(
            template
        )
        target_models[component.component_id] = (
            build_metric_target_model_from_template(
                template
            )
        )

    return target_models


def select_wom_metric_components_for_group(components, group_id):
    return select_components(
        components,
        ComponentSelectionCriteria(
            component_types={
                TileComponentType.WOM_METRIC,
            },
            any_groups={
                group_id,
            },
            supported_recipe_ids={
                GenerationRecipeId.N_OF.value,
            },
        ),
    )


def build_wom_metric_group_n_of_candidate(
    components,
    target_model_by_component_id,
    group_id,
    point_value,
    required_route_count,
    title,
    explanation=(),
):
    selected_components = select_wom_metric_components_for_group(
        components,
        group_id,
    )

    require_component_count(
        selected_components,
        required_route_count,
        label=f"{group_id} components",
    )

    return build_n_of_tile_candidate(
        components=selected_components,
        point_value=point_value,
        target_model_by_component_id=target_model_by_component_id,
        required_route_count=required_route_count,
        title=title,
        explanation=explanation,
    )


def build_skilling_minigame_sampler_candidate(
    point_value=3,
    required_route_count=2,
):
    return build_wom_metric_group_n_of_candidate(
        components=get_static_metric_components(),
        target_model_by_component_id=get_static_metric_target_models_by_component_id(),
        group_id="skilling_minigames",
        point_value=point_value,
        required_route_count=required_route_count,
        title="Skilling minigame sampler",
        explanation=(
            "Generated from WOM metric components in the skilling_minigames group.",
        ),
    )
