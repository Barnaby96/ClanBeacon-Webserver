"""Regression tests for candidate-level route accessibility."""

from dataclasses import replace

from utils.board_generation import RouteMode
from utils.osrs_tile_catalogue import (
    get_curated_tile_generation_candidates,
)


def _candidate(mode):
    return next(
        candidate
        for candidate in get_curated_tile_generation_candidates()
        if candidate.route_mode == mode
    )


def test_single_route_requires_access():
    from utils.osrs_player_access import (
        assess_candidate_route_access,
    )

    candidate = _candidate(RouteMode.SINGLE)

    assert assess_candidate_route_access(
        candidate, ("accessible",)
    ) == "accessible"

    assert assess_candidate_route_access(
        candidate, ("inaccessible",)
    ) == "inaccessible"

    assert assess_candidate_route_access(
        candidate, ("unknown",)
    ) == "unknown"


def test_or_accepts_one_accessible_route():
    from utils.osrs_player_access import (
        assess_candidate_route_access,
    )

    candidate = _candidate(RouteMode.OR)
    assert len(candidate.routes) == 2

    assert assess_candidate_route_access(
        candidate, ("inaccessible", "accessible")
    ) == "accessible"

    assert assess_candidate_route_access(
        candidate, ("inaccessible", "unknown")
    ) == "unknown"

    assert assess_candidate_route_access(
        candidate, ("inaccessible", "inaccessible")
    ) == "inaccessible"


def test_and_requires_every_route():
    from utils.osrs_player_access import (
        assess_candidate_route_access,
    )

    # AND is not yet in the active catalogue.
    # Use real route definitions in a synthetic AND candidate.
    candidate = replace(
        _candidate(RouteMode.OR),
        route_mode=RouteMode.AND,
    )

    assert assess_candidate_route_access(
        candidate, ("accessible", "accessible")
    ) == "accessible"

    assert assess_candidate_route_access(
        candidate, ("accessible", "unknown")
    ) == "unknown"

    # One demonstrably blocked mandatory route makes
    # the AND objective inaccessible.
    assert assess_candidate_route_access(
        candidate, ("inaccessible", "unknown")
    ) == "inaccessible"


def test_sum_can_use_one_repeatable_contributing_route():
    from utils.osrs_player_access import (
        assess_candidate_route_access,
    )

    candidate = _candidate(RouteMode.SUM)

    # The existing SUM examples are repeatable clue-scroll
    # tiers sharing a single completion target.
    assert len(candidate.routes) == 4

    assert assess_candidate_route_access(
        candidate,
        (
            "accessible",
            "inaccessible",
            "inaccessible",
            "unknown",
        ),
    ) == "accessible"

    assert assess_candidate_route_access(
        candidate,
        (
            "inaccessible",
            "inaccessible",
            "unknown",
            "inaccessible",
        ),
    ) == "unknown"

    assert assess_candidate_route_access(
        candidate,
        ("inaccessible",) * 4,
    ) == "inaccessible"


def test_n_of_requires_enough_accessible_routes():
    from utils.osrs_player_access import (
        assess_candidate_route_access,
    )

    candidate = _candidate(RouteMode.N_OF)

    assert len(candidate.routes) == 3
    assert candidate.required_route_count == 2

    assert assess_candidate_route_access(
        candidate,
        ("accessible", "accessible", "inaccessible"),
    ) == "accessible"

    assert assess_candidate_route_access(
        candidate,
        ("accessible", "unknown", "inaccessible"),
    ) == "unknown"

    # One unknown route cannot make up for two blocked
    # routes when two completions are required.
    assert assess_candidate_route_access(
        candidate,
        ("inaccessible", "inaccessible", "unknown"),
    ) == "inaccessible"

    assert assess_candidate_route_access(
        candidate,
        ("inaccessible",) * 3,
    ) == "inaccessible"


def test_route_assessment_fails_closed_on_invalid_evidence():
    from utils.osrs_player_access import (
        assess_candidate_route_access,
    )

    candidate = _candidate(RouteMode.OR)

    # Route assessments must correspond to every route
    # in the candidate, in the same order.
    assert assess_candidate_route_access(
        candidate,
        ("accessible",),
    ) == "unknown"

    assert assess_candidate_route_access(
        candidate,
        ("accessible", "inaccessible", "accessible"),
    ) == "unknown"

    assert assess_candidate_route_access(
        candidate,
        (True, "inaccessible"),
    ) == "unknown"

    assert assess_candidate_route_access(
        candidate,
        ("not_checked", "inaccessible"),
    ) == "unknown"

    assert assess_candidate_route_access(
        candidate,
        None,
    ) == "unknown"
