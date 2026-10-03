from decimal import Decimal

from utils.board_generation import (
    ContributionMode,
    Route,
    RouteMode,
    TileCandidate,
    TileCategory,
    TrackingSource,
)


def build_drop_route(expected_rolls=None):
    return Route(
        route_type=TileCategory.DROP,
        display_text="Obtain a thing",
        target=1,
        tracking_source=TrackingSource.DINK,
        contribution_mode=ContributionMode.TEAM_SUM,
        expected_rolls=expected_rolls,
    )


def test_single_route_candidate_exposes_expected_rolls():
    candidate = TileCandidate(
        title="Obtain a thing",
        point_value=1,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.SINGLE,
        routes=(
            build_drop_route(
                Decimal("50")
            ),
        ),
    )

    assert candidate.route_expected_rolls == (
        Decimal("50"),
    )
    assert candidate.expected_rolls == Decimal(
        "50"
    )


def test_or_candidate_expected_rolls_requires_all_routes_to_be_estimated():
    candidate = TileCandidate(
        title="Obtain a thing or another thing",
        point_value=1,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.OR,
        routes=(
            build_drop_route(
                Decimal("50")
            ),
            build_drop_route(),
        ),
    )

    assert candidate.expected_rolls is None


def test_n_of_candidate_expected_rolls_uses_easiest_required_routes():
    routes = tuple(
        build_drop_route(
            Decimal(
                str(
                    expected_rolls
                )
            )
        )
        for expected_rolls in (
            100,
            25,
            50,
        )
    )

    candidate = TileCandidate(
        title="Complete 2 of 3",
        point_value=2,
        primary_category=TileCategory.DROP,
        route_mode=RouteMode.N_OF,
        routes=routes,
        required_route_count=2,
    )

    assert candidate.expected_rolls == Decimal(
        "75"
    )
