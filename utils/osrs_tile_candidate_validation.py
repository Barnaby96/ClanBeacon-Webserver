"""Common validation for generated OSRS Bingo tile candidates."""

from collections import Counter
from dataclasses import dataclass

from utils.board_generation import (
    RouteMode,
    TileCategory,
    TrackingSource,
    canonical_id,
)


@dataclass(frozen=True)
class TileCandidateValidationIssue:
    candidate_title: str
    message: str


def enum_value(value):
    return getattr(
        value,
        "value",
        value,
    )


def route_condition_signature(route):
    return (
        enum_value(
            route.route_type
        ),
        canonical_id(
            route.metric_id
        ),
        canonical_id(
            route.source_id
        ),
        canonical_id(
            route.skill_id
        ),
        canonical_id(
            route.boss_id
        ),
        canonical_id(
            route.drop_id
        ),
        canonical_id(
            route.drop_group_id
        ),
        canonical_id(
            route.pet_id
        ),
        canonical_id(
            route.pet_group_id
        ),
    )


def is_meaningful_route_signature(signature):
    return any(
        value
        for value in signature[1:]
    )


def validate_route(route, route_number):
    errors = []

    if not route.display_text:
        errors.append(
            f"Route {route_number} requires display text."
        )

    if route.target <= 0:
        errors.append(
            f"Route {route_number} target must be positive."
        )

    try:
        TileCategory(
            route.route_type
        )
    except ValueError:
        errors.append(
            f"Route {route_number} has unknown route type."
        )

    try:
        TrackingSource(
            route.tracking_source
        )
    except ValueError:
        errors.append(
            f"Route {route_number} has unknown tracking source."
        )

    return tuple(
        errors
    )


def validate_duplicate_route_conditions(candidate):
    signatures = [
        route_condition_signature(
            route
        )
        for route in candidate.routes
    ]

    meaningful_signatures = [
        signature
        for signature in signatures
        if is_meaningful_route_signature(
            signature
        )
    ]

    duplicate_signatures = [
        signature
        for signature, count in Counter(
            meaningful_signatures
        ).items()
        if count > 1
    ]

    if duplicate_signatures:
        return (
            "Candidate contains duplicate route conditions.",
        )

    return ()


def validate_route_mode_requirements(candidate):
    if candidate.route_mode != RouteMode.N_OF:
        return ()

    if candidate.required_route_count is None:
        return (
            "N_OF candidates require required_route_count.",
        )

    if candidate.required_route_count < 1:
        return (
            "N_OF required_route_count must be positive.",
        )

    if candidate.required_route_count > len(
        candidate.routes
    ):
        return (
            "N_OF required_route_count cannot exceed route count.",
        )

    return ()


def validate_tile_candidate(candidate):
    errors = list(
        candidate.validation_errors()
    )

    for route_number, route in enumerate(
        candidate.routes,
        start=1,
    ):
        errors.extend(
            validate_route(
                route,
                route_number,
            )
        )

    errors.extend(
        validate_duplicate_route_conditions(
            candidate
        )
    )
    errors.extend(
        validate_route_mode_requirements(
            candidate
        )
    )

    return tuple(
        errors
    )


def assert_valid_tile_candidate(candidate):
    errors = validate_tile_candidate(
        candidate
    )

    if errors:
        raise ValueError(
            "; ".join(
                errors
            )
        )

    return candidate


def validate_tile_candidate_pool(candidates):
    issues = []

    for candidate in candidates:
        for error in validate_tile_candidate(
            candidate
        ):
            issues.append(
                TileCandidateValidationIssue(
                    candidate_title=candidate.title,
                    message=error,
                )
            )

    return tuple(
        issues
    )


def assert_valid_tile_candidate_pool(candidates):
    issues = validate_tile_candidate_pool(
        candidates
    )

    if issues:
        raise ValueError(
            "; ".join(
                f"{issue.candidate_title}: {issue.message}"
                for issue in issues
            )
        )

    return tuple(
        candidates
    )
