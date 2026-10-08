from utils.board_generation import (
    RouteMode,
    TileCategory,
    canonical_id,
)
from utils.osrs_drop_groups import (
    DROP_GROUP_DEFINITIONS,
    get_drop_group_definition,
)
from utils.osrs_generated_board_preview import (
    get_candidate_by_generated_board_key,
)
from utils.osrs_tile_catalogue import (
    get_curated_tile_generation_candidates,
)
from utils.osrs_pets import get_osrs_pet_options
from utils.osrs_tile_template_expansion import (
    STATIC_SKILL_XP_TEMPLATES,
)


def _get_drop_name(drop_id):
    matching_names = {
        drop_name
        for definition in DROP_GROUP_DEFINITIONS
        for definition_drop_id, drop_name in zip(
            definition.distinct_drop_ids,
            definition.distinct_drop_names,
        )
        if definition_drop_id == drop_id
    }

    if not matching_names:
        raise ValueError(
            f"Unknown generated drop ID: {drop_id}"
        )

    if len(matching_names) != 1:
        raise ValueError(
            f"Generated drop ID '{drop_id}' has conflicting names."
        )

    return next(iter(matching_names))


def _get_skill_name(skill_id):
    matching_names = {
        template.skill_name
        for template in STATIC_SKILL_XP_TEMPLATES
        if template.skill_id.casefold() == str(
            skill_id
        ).casefold()
    }

    if not matching_names:
        raise ValueError(
            f"Unknown generated skill ID: {skill_id}"
        )

    if len(matching_names) != 1:
        raise ValueError(
            f"Generated skill ID '{skill_id}' has conflicting names."
        )

    return next(iter(matching_names))


def _get_pet_name(pet_id):
    canonical_pet_id = canonical_id(
        pet_id
    )

    matching_names = {
        option["value"]
        for option in get_osrs_pet_options()
        if canonical_id(
            option["value"]
        ) == canonical_pet_id
    }

    if not matching_names:
        raise ValueError(
            f"Unknown generated pet ID: {pet_id}"
        )

    if len(matching_names) != 1:
        raise ValueError(
            f"Generated pet ID '{pet_id}' has conflicting names."
        )

    return next(iter(matching_names))


def _build_live_condition(route, completion_path):
    if route.route_type == TileCategory.SKILL:
        if route.metric_id is None:
            raise ValueError(
                "Generated SKILL routes require a WOM metric."
            )

        condition_type = "EXPERIENCE"
        condition_trigger = route.metric_id
    elif route.route_type == TileCategory.PET:
        condition_type = "PET"
        condition_trigger = _get_pet_name(
            route.pet_id
        )
    elif route.route_type == TileCategory.HYBRID:
        condition_type = "METRIC"
        condition_trigger = route.metric_id
    elif route.route_type == TileCategory.KILLCOUNT:
        if route.boss_id is None:
            raise ValueError(
                "Generated KILLCOUNT routes require a boss ID."
            )

        condition_type = "KILLCOUNT"
        condition_trigger = route.boss_id
    elif route.route_type == TileCategory.DROP:
        if route.drop_id is None:
            raise ValueError(
                "Specific DROP routes require a drop ID."
            )

        condition_type = "DROP"
        condition_trigger = _get_drop_name(
            route.drop_id
        )
    else:
        raise ValueError(
            f"Unsupported generated route type: {route.route_type}"
        )

    return {
        "completion_path": completion_path,
        "condition_type": condition_type,
        "condition_trigger": condition_trigger,
        "target": int(route.target),
    }


def _build_drop_group_conditions(route, completion_path):
    definition = get_drop_group_definition(
        route.drop_group_id
    )

    if definition is None:
        raise ValueError(
            f"Unknown generated drop group: {route.drop_group_id}"
        )

    if not definition.distinct_drop_names:
        raise ValueError(
            f"Generated drop group '{route.drop_group_id}' "
            "does not contain Dink-facing drop names."
        )

    return [
        {
            "completion_path": completion_path,
            "condition_type": "DROP",
            "condition_trigger": drop_name,
            "target": 1,
        }
        for drop_name in definition.distinct_drop_names
    ]


def build_live_tile_payload_from_candidate(candidate):
    if candidate.route_mode == RouteMode.SINGLE:
        route = candidate.routes[0]

        if (
            route.route_type == TileCategory.DROP
            and route.drop_id is None
            and route.drop_group_id is not None
        ):
            conditions = _build_drop_group_conditions(
                route,
                completion_path=1,
            )
            completion_paths = [
                {
                    "completion_path": 1,
                    "route_mode": "N_OF",
                    "route_target": int(route.target),
                    "require_unique": True,
                }
            ]
        else:
            conditions = [
                _build_live_condition(
                    route,
                    completion_path=1,
                )
            ]
            completion_paths = [
                {
                    "completion_path": 1,
                    "route_mode": "ALL",
                    "route_target": None,
                    "require_unique": False,
                }
            ]

        tile_rules = route.display_text

    elif candidate.route_mode == RouteMode.OR:
        conditions = []
        completion_paths = []

        for path_number, route in enumerate(
            candidate.routes,
            start=1,
        ):
            conditions.append(
                _build_live_condition(
                    route,
                    completion_path=path_number,
                )
            )
            completion_paths.append(
                {
                    "completion_path": path_number,
                    "route_mode": "ALL",
                    "route_target": None,
                    "require_unique": False,
                }
            )

        tile_rules = " OR ".join(
            route.display_text
            for route in candidate.routes
        )

    elif candidate.route_mode == RouteMode.SUM:
        route_targets = {
            int(route.target)
            for route in candidate.routes
        }

        if len(route_targets) != 1:
            raise ValueError(
                "SUM generated routes must share one target."
            )

        route_target = next(
            iter(route_targets)
        )

        conditions = [
            _build_live_condition(
                route,
                completion_path=1,
            )
            for route in candidate.routes
        ]

        completion_paths = [
            {
                "completion_path": 1,
                "route_mode": "SUM",
                "route_target": route_target,
                "require_unique": False,
            }
        ]

        tile_rules = candidate.title

    elif candidate.route_mode == RouteMode.N_OF:
        conditions = [
            _build_live_condition(
                route,
                completion_path=1,
            )
            for route in candidate.routes
        ]

        completion_paths = [
            {
                "completion_path": 1,
                "route_mode": "N_OF",
                "route_target": candidate.required_route_count,
                "require_unique": False,
            }
        ]

        tile_rules = (
            f"Complete {candidate.required_route_count} of: "
            + "; ".join(
                route.display_text
                for route in candidate.routes
            )
        )

    else:
        raise ValueError(
            "Only SINGLE, OR, SUM and N_OF generated routes "
            "are supported currently."
        )

    return {
        "tile_name": candidate.title,
        "tile_points": candidate.point_value,
        "tile_rules": tile_rules,
        "conditions": conditions,
        "completion_paths": completion_paths,
    }





def build_live_tile_payloads_from_generated_board_keys(
    tile_keys,
):
    tile_keys = tuple(tile_keys)

    candidates = get_curated_tile_generation_candidates()
    candidate_by_key = get_candidate_by_generated_board_key(
        candidates
    )

    unknown_tile_keys = [
        tile_key
        for tile_key in tile_keys
        if tile_key not in candidate_by_key
    ]

    if unknown_tile_keys:
        raise ValueError(
            "One or more generated board tiles are no longer "
            "available in the curated catalogue."
        )

    return tuple(
        build_live_tile_payload_from_candidate(
            candidate_by_key[tile_key]
        )
        for tile_key in tile_keys
    )
